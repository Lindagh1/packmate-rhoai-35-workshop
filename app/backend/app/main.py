from __future__ import annotations

import asyncio
import logging
import os
import uuid
from collections.abc import AsyncIterator

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.agent.exceptions import AgentResponseError, LLMConfigurationError
from app.agent.progress import ProgressStage
from app.agent.service import AgentService
from app.models.chat import ChatRequest, PackingResponse
from app.models.weather import WeatherResponse
from app.observability import (
    HTTP_DURATION,
    HTTP_REQUESTS,
    PACKMATE_VERSION,
    STREAM_COMPLETED,
    STREAM_DISCONNECTS,
    STREAM_DURATION,
    STREAM_ERRORS,
    STREAM_HEARTBEATS,
    STREAM_REQUESTS,
    STREAM_TTFE,
    Timer,
    metrics_payload,
    setup_telemetry,
    span,
)
from app.streaming import (
    format_sse,
    format_sse_comment,
    packing_response_json,
    sanitize_public_error_message,
)
from app.tools.weather import CityNotFoundError, WeatherToolError, get_weather

logger = logging.getLogger(__name__)

# Max silence between SSE frames (AWS Classic ELB idle is ~60s).
HEARTBEAT_INTERVAL_SECONDS = float(os.getenv("PACKMATE_STREAM_HEARTBEAT_SECONDS", "10"))

app = FastAPI(title="Packmate API", version=PACKMATE_VERSION)
agent_service = AgentService()
setup_telemetry(app)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        timer = Timer()
        response = await call_next(request)
        endpoint = request.url.path
        if endpoint not in {"/metrics"}:
            HTTP_REQUESTS.labels(
                method=request.method,
                endpoint=endpoint,
                status=str(response.status_code),
            ).inc()
            HTTP_DURATION.labels(method=request.method, endpoint=endpoint).observe(
                timer.seconds()
            )
        return response


app.add_middleware(MetricsMiddleware)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, str]:
    """Readiness: app can accept requests (does not require external LLM)."""
    return {"status": "ready", "version": PACKMATE_VERSION}


@app.get("/metrics")
def metrics() -> Response:
    payload, content_type = metrics_payload()
    return Response(content=payload, media_type=content_type)


@app.get("/api/v1/weather", response_model=WeatherResponse)
async def weather(
    city: str = Query(..., min_length=1),
    days: int = Query(default=14, ge=1, le=14),
) -> WeatherResponse:
    try:
        return await get_weather(city, days)
    except CityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WeatherToolError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/v1/chat", response_model=PackingResponse)
async def chat(request: ChatRequest) -> PackingResponse:
    try:
        return await agent_service.chat(request.message, request.traveler_profile)
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AgentResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _error_code_for_exception(exc: BaseException) -> str:
    if isinstance(exc, LLMConfigurationError):
        return "llm_not_configured"
    if isinstance(exc, AgentResponseError):
        return "agent_error"
    if isinstance(exc, asyncio.CancelledError):
        return "cancelled"
    return "internal_error"


async def _stream_chat_events(
    http_request: Request,
    body: ChatRequest,
) -> AsyncIterator[str]:
    trace_id = uuid.uuid4().hex[:16]
    STREAM_REQUESTS.inc()
    timer = Timer()
    first_event_sent = False
    queue: asyncio.Queue[tuple[str, object] | None] = asyncio.Queue()

    async def on_progress(stage: ProgressStage) -> None:
        await queue.put(("progress", {"stage": stage}))

    async def run_agent() -> None:
        try:
            with span("chat.stream.agent", {"trace_id": trace_id}):
                result = await agent_service.chat(
                    body.message,
                    body.traveler_profile,
                    on_progress=on_progress,
                )
            await queue.put(("completed", result))
        except asyncio.CancelledError:
            await queue.put(("cancelled", None))
            raise
        except Exception as exc:  # noqa: BLE001 — sanitized for SSE
            await queue.put(("error", exc))
        finally:
            await queue.put(None)

    task = asyncio.create_task(run_agent())

    def _mark_first() -> None:
        nonlocal first_event_sent
        if not first_event_sent:
            STREAM_TTFE.observe(timer.seconds())
            first_event_sent = True

    try:
        started = format_sse(
            "started",
            {"status": "processing", "trace_id": trace_id},
        )
        _mark_first()
        yield started

        while True:
            if await http_request.is_disconnected():
                STREAM_DISCONNECTS.inc()
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                logger.info("stream client disconnected trace_id=%s", trace_id)
                return

            try:
                item = await asyncio.wait_for(
                    queue.get(),
                    timeout=HEARTBEAT_INTERVAL_SECONDS,
                )
            except TimeoutError:
                STREAM_HEARTBEATS.inc()
                yield format_sse("heartbeat", {"status": "processing"})
                yield format_sse_comment("keepalive")
                continue

            if item is None:
                break

            kind, payload = item
            if kind == "progress":
                yield format_sse("progress", payload)  # type: ignore[arg-type]
            elif kind == "completed":
                STREAM_COMPLETED.inc()
                yield format_sse(
                    "completed",
                    packing_response_json(payload),
                )
            elif kind == "cancelled":
                STREAM_DISCONNECTS.inc()
                return
            elif kind == "error":
                exc = payload
                assert isinstance(exc, BaseException)
                code = _error_code_for_exception(exc)
                _, message = sanitize_public_error_message(str(exc), code=code)
                if isinstance(exc, LLMConfigurationError):
                    message = "The language model is not configured."
                    code = "llm_not_configured"
                STREAM_ERRORS.labels(code=code).inc()
                yield format_sse(
                    "error",
                    {"code": code, "message": message, "trace_id": trace_id},
                )
    finally:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        STREAM_DURATION.observe(timer.seconds())


@app.post("/api/v1/chat/stream")
async def chat_stream(http_request: Request, body: ChatRequest) -> StreamingResponse:
    generator = _stream_chat_events(http_request, body)
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
