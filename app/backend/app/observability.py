from __future__ import annotations

import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "packmate-backend")
PACKMATE_VERSION = os.getenv("PACKMATE_VERSION", "dev")

HTTP_REQUESTS = Counter(
    "packmate_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)
HTTP_DURATION = Histogram(
    "packmate_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
)
LLM_REQUESTS = Counter(
    "packmate_llm_requests_total",
    "Total LLM requests",
    ["status"],
)
LLM_DURATION = Histogram(
    "packmate_llm_request_duration_seconds",
    "LLM request duration in seconds",
)
LLM_ERRORS = Counter(
    "packmate_llm_errors_total",
    "Total LLM errors",
    ["error_type"],
)
TOOL_CALLS = Counter(
    "packmate_tool_calls_total",
    "Total tool calls",
    ["tool", "status"],
)
TOOL_DURATION = Histogram(
    "packmate_tool_call_duration_seconds",
    "Tool call duration in seconds",
    ["tool"],
)
INVALID_RESPONSES = Counter(
    "packmate_invalid_responses_total",
    "Total invalid agent responses",
)
AGENT_RETRIES = Counter(
    "packmate_agent_retries_total",
    "Total bounded agent retries started for transient failures",
)
AGENT_RETRY_SUCCESS = Counter(
    "packmate_agent_retry_success_total",
    "Total agent requests that succeeded after a bounded retry",
)
AGENT_RETRY_EXHAUSTED = Counter(
    "packmate_agent_retry_exhausted_total",
    "Total agent requests that exhausted the bounded retry budget",
)
BAGGAGE_WARNINGS = Counter(
    "packmate_baggage_warnings_total",
    "Total baggage warnings emitted",
)
STREAM_REQUESTS = Counter(
    "packmate_stream_requests_total",
    "Total streaming chat requests",
)
STREAM_COMPLETED = Counter(
    "packmate_stream_completed_total",
    "Total streaming chat completions",
)
STREAM_ERRORS = Counter(
    "packmate_stream_errors_total",
    "Total streaming chat errors",
    ["code"],
)
STREAM_DISCONNECTS = Counter(
    "packmate_stream_client_disconnects_total",
    "Total streaming client disconnects",
)
STREAM_DURATION = Histogram(
    "packmate_stream_duration_seconds",
    "Streaming chat duration in seconds",
)
STREAM_HEARTBEATS = Counter(
    "packmate_stream_heartbeats_total",
    "Total streaming heartbeats emitted",
)
STREAM_TTFE = Histogram(
    "packmate_stream_time_to_first_event_seconds",
    "Time to first SSE event in seconds",
)

_tracer = None
_otel_enabled = False


def setup_telemetry(app: Any) -> None:
    """Configure OpenTelemetry if an exporter is enabled; always safe no-op otherwise."""
    global _tracer, _otel_enabled

    exporter = (os.getenv("OTEL_TRACES_EXPORTER") or "none").strip().lower()
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()

    if exporter in {"", "none"} and not endpoint:
        _otel_enabled = False
        _tracer = None
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        resource = Resource.create(
            {
                "service.name": SERVICE_NAME,
                "service.version": PACKMATE_VERSION,
            }
        )
        provider = TracerProvider(resource=resource)

        if endpoint:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        elif exporter == "console":
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer("packmate.backend")
        FastAPIInstrumentor.instrument_app(app, excluded_urls="health,ready,metrics")
        HTTPXClientInstrumentor().instrument()
        _otel_enabled = True
    except Exception:
        # Observability must never break the API.
        _otel_enabled = False
        _tracer = None


@contextmanager
def span(name: str, attributes: dict[str, Any] | None = None) -> Iterator[None]:
    """Create a sanitized span when OTel is enabled."""
    attrs = _sanitize_attributes(attributes or {})
    if _tracer is None:
        yield
        return
    with _tracer.start_as_current_span(name) as current:
        for key, value in attrs.items():
            current.set_attribute(key, value)
        yield


def _sanitize_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    blocked = ("message", "prompt", "note", "medical", "token", "password", "api_key", "body")
    cleaned: dict[str, Any] = {}
    for key, value in attributes.items():
        lowered = key.lower()
        if any(token in lowered for token in blocked):
            continue
        if isinstance(value, (str, int, float, bool)):
            cleaned[key] = value
    return cleaned


def metrics_payload() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST


class Timer:
    def __init__(self) -> None:
        self._start = time.perf_counter()

    def seconds(self) -> float:
        return time.perf_counter() - self._start
