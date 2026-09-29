import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.agent.config import LLMSettings
from app.agent.exceptions import AgentResponseError, LLMConfigurationError, ParseError
from app.agent.parser import clean_model_output, parse_packing_response
from app.agent.service import AgentService
from app.main import app
from app.models.chat import PackingResponse
from app.models.weather import ForecastDay, WeatherResponse
from tests.helpers import make_tool_call

client = TestClient(app)

VALID_PACKING_PAYLOAD = {
    "destination": "Rome",
    "start_date": "2026-07-21",
    "end_date": "2026-07-23",
    "weather_summary": {
        "location": "Rome",
        "overview": "Chaud et ensoleillé avec quelques nuages.",
        "min_temperature": "18°C",
        "max_temperature": "32°C",
        "conditions": "Mainly Clear",
    },
    "packing_items": [
        {
            "name": "T-shirt",
            "category": "Clothes",
            "quantity": 3,
            "reason": "Temps chaud pendant 3 jours",
            "essential": True,
        }
    ],
    "warnings": ["Bagage cabine : liquides limités à 100 ml"],
    "baggage_warnings": [],
    "profile_considerations": [],
    "rules_disclaimer": "DEMONSTRATION RULES ONLY.",
    "language": "fr",
}

VALID_PACKING_JSON = json.dumps(VALID_PACKING_PAYLOAD)


def _configured_settings() -> LLMSettings:
    return LLMSettings(
        base_url="https://example.com/v1",
        model="test-model",
        api_key="test-key",
    )


def _make_tool_call(
    tool_id: str = "call_weather_1",
    name: str = "get_weather",
    arguments: dict | None = None,
    city: str = "Rome",
    days: int = 7,
) -> SimpleNamespace:
    if arguments is None:
        arguments = {"city": city, "days": days}

    return make_tool_call(tool_id, name, arguments)


def _make_message(
    content: str | None = None,
    tool_calls: list[MagicMock] | None = None,
) -> MagicMock:
    message = MagicMock()
    message.content = content
    message.tool_calls = tool_calls
    return message


def _make_completion(message: MagicMock) -> MagicMock:
    completion = MagicMock()
    completion.choices = [MagicMock(message=message)]
    return completion


def _mock_openai_client(responses: list[MagicMock]) -> MagicMock:
    mock_client = MagicMock()
    mock_client.chat.completions.create = MagicMock(side_effect=responses)
    return mock_client


@pytest.mark.asyncio
async def test_agent_returns_valid_structured_response() -> None:
    mock_client = _mock_openai_client(
        [
            _make_completion(_make_message(tool_calls=[_make_tool_call()])),
            _make_completion(_make_message(content=VALID_PACKING_JSON, tool_calls=None)),
        ]
    )
    weather_result = WeatherResponse(
        location="Rome",
        forecast=[
            ForecastDay(
                date="2026-07-21",
                min="18°C",
                max="32°C",
                condition="Mainly Clear 🌤",
            )
        ],
    )

    service = AgentService(settings=_configured_settings(), client=mock_client)

    weather_adapter = AsyncMock()
    weather_adapter.get_weather = AsyncMock(return_value=weather_result)
    with patch("app.agent.tools.build_weather_adapter", return_value=weather_adapter):
        result = await service.chat(
            "Je pars à Rome pendant trois jours la semaine prochaine avec un bagage cabine"
        )

    assert isinstance(result, PackingResponse)
    assert result.destination == "Rome"
    assert result.language == "fr"
    assert len(result.packing_items) == 1
    assert result.packing_items[0].essential is True
    assert mock_client.chat.completions.create.call_count == 2


@pytest.mark.asyncio
async def test_agent_calls_weather_tool() -> None:
    mock_client = _mock_openai_client(
        [
            _make_completion(_make_message(tool_calls=[_make_tool_call(city="Rome", days=7)])),
            _make_completion(_make_message(content=VALID_PACKING_JSON, tool_calls=None)),
        ]
    )
    weather_result = WeatherResponse(location="Rome", forecast=[])
    weather_adapter = AsyncMock()
    weather_adapter.get_weather = AsyncMock(return_value=weather_result)

    service = AgentService(settings=_configured_settings(), client=mock_client)

    with patch("app.agent.tools.build_weather_adapter", return_value=weather_adapter):
        await service.chat("Je pars à Rome la semaine prochaine")

    weather_adapter.get_weather.assert_awaited_once_with("Rome", 7)


@pytest.mark.asyncio
async def test_agent_retries_after_invalid_json_then_succeeds() -> None:
    mock_client = _mock_openai_client(
        [
            _make_completion(_make_message(tool_calls=[_make_tool_call()])),
            _make_completion(_make_message(content="not valid json", tool_calls=None)),
            _make_completion(_make_message(content=VALID_PACKING_JSON, tool_calls=None)),
        ]
    )
    weather_result = WeatherResponse(location="Rome", forecast=[])
    weather_adapter = AsyncMock()
    weather_adapter.get_weather = AsyncMock(return_value=weather_result)

    service = AgentService(settings=_configured_settings(), client=mock_client)

    with patch("app.agent.tools.build_weather_adapter", return_value=weather_adapter):
        result = await service.chat("Je pars à Rome")

    assert result.destination == "Rome"
    assert mock_client.chat.completions.create.call_count == 3


@pytest.mark.asyncio
async def test_agent_fails_after_multiple_invalid_responses() -> None:
    mock_client = _mock_openai_client(
        [
            _make_completion(_make_message(tool_calls=[_make_tool_call()])),
            _make_completion(_make_message(content="still not json", tool_calls=None)),
            _make_completion(_make_message(content='{"incomplete": true}', tool_calls=None)),
            _make_completion(_make_message(content="nope", tool_calls=None)),
            _make_completion(_make_message(content="still nope", tool_calls=None)),
            # Bounded outer retry reuses the weather cache; model asks again then fails parse.
            _make_completion(
                _make_message(tool_calls=[_make_tool_call(tool_id="call_weather_retry")])
            ),
            _make_completion(_make_message(content="still not json", tool_calls=None)),
            _make_completion(_make_message(content='{"incomplete": true}', tool_calls=None)),
            _make_completion(_make_message(content="nope", tool_calls=None)),
            _make_completion(_make_message(content="still nope", tool_calls=None)),
        ]
    )
    weather_result = WeatherResponse(location="Rome", forecast=[])
    weather_adapter = AsyncMock()
    weather_adapter.get_weather = AsyncMock(return_value=weather_result)

    service = AgentService(settings=_configured_settings(), client=mock_client)

    with (
        patch("app.agent.tools.build_weather_adapter", return_value=weather_adapter),
        patch("app.agent.service.retry_delay_seconds", return_value=0),
    ):
        with pytest.raises(AgentResponseError, match="Invalid agent response after 4 attempts"):
            await service.chat("Je pars à Rome")

    assert weather_adapter.get_weather.await_count == 1


@pytest.mark.asyncio
async def test_missing_credentials_raise_configuration_error() -> None:
    service = AgentService(
        settings=LLMSettings(base_url=None, model=None, api_key=None),
        client=MagicMock(),
    )

    with pytest.raises(LLMConfigurationError, match="BASE_URL"):
        await service.chat("Bonjour")


def test_app_starts_without_llm_credentials() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_endpoint_returns_structured_response() -> None:
    mock_response = PackingResponse.model_validate(VALID_PACKING_PAYLOAD)

    with patch("app.main.agent_service.chat", AsyncMock(return_value=mock_response)):
        response = client.post(
            "/api/v1/chat",
            json={"message": "Je pars à Rome pendant trois jours la semaine prochaine"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["destination"] == "Rome"
    assert body["language"] == "fr"
    assert body["packing_items"][0]["name"] == "T-shirt"
    assert body["warnings"] == ["Bagage cabine : liquides limités à 100 ml"]


def test_chat_endpoint_returns_503_without_credentials() -> None:
    unconfigured = AgentService(
        settings=LLMSettings(base_url=None, model=None, api_key=None),
    )

    with patch("app.main.agent_service", unconfigured):
        response = client.post(
            "/api/v1/chat",
            json={"message": "Je pars à Rome"},
        )

    assert response.status_code == 503
    assert "BASE_URL" in response.json()["detail"]


def test_chat_endpoint_returns_502_on_agent_failure() -> None:
    with patch(
        "app.main.agent_service.chat",
        AsyncMock(side_effect=AgentResponseError("Invalid agent response")),
    ):
        response = client.post(
            "/api/v1/chat",
            json={"message": "Je pars à Rome"},
        )

    assert response.status_code == 502
    assert response.json()["detail"] == "Invalid agent response"


def test_parser_strips_redacted_thinking_tags() -> None:
    wrapped = f"<think>secret reasoning</think>{VALID_PACKING_JSON}"
    result = parse_packing_response(wrapped)

    assert result.destination == "Rome"


def test_parser_extracts_json_from_markdown_fence() -> None:
    wrapped = f"```json\n{VALID_PACKING_JSON}\n```"
    result = parse_packing_response(wrapped)

    assert result.destination == "Rome"


def test_parser_raises_on_invalid_json() -> None:
    with pytest.raises(ParseError, match="Invalid JSON"):
        parse_packing_response("not-json")


def test_parser_coerces_stringified_list_fields() -> None:
    """Some models emit list fields as JSON strings instead of arrays."""
    payload = {
        **VALID_PACKING_PAYLOAD,
        "packing_items": json.dumps(VALID_PACKING_PAYLOAD["packing_items"]),
        "baggage_warnings": "[]",
        "profile_considerations": "[]",
        "warnings": json.dumps(VALID_PACKING_PAYLOAD["warnings"]),
        "weather_summary": json.dumps(VALID_PACKING_PAYLOAD["weather_summary"]),
    }

    result = parse_packing_response(json.dumps(payload))

    assert result.destination == "Rome"
    assert len(result.packing_items) == 1
    assert result.packing_items[0].name == "T-shirt"
    assert result.baggage_warnings == []
    assert result.profile_considerations == []
    assert result.warnings == ["Bagage cabine : liquides limités à 100 ml"]
    assert result.weather_summary.location == "Rome"


def test_parser_repairs_invalid_unicode_escapes() -> None:
    broken = VALID_PACKING_JSON.replace("Rome", "Rom\\uXXXe", 1)
    result = parse_packing_response(broken)

    assert "Rom" in result.destination


def test_clean_model_output_removes_thinking_tags() -> None:
    cleaned = clean_model_output("<think>x</think> hello")

    assert cleaned == "hello"
