from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.weather import ForecastDay, WeatherResponse
from app.tools.weather import CityNotFoundError, WeatherToolError, get_weather

client = TestClient(app)

GEO_RESPONSE = {
    "results": [
        {
            "name": "Paris",
            "latitude": 48.85341,
            "longitude": 2.3488,
        }
    ]
}

FORECAST_RESPONSE = {
    "daily": {
        "time": ["2026-07-15", "2026-07-16", "2026-07-17"],
        "temperature_2m_min": [15.2, 16.1, 14.8],
        "temperature_2m_max": [25.4, 26.0, 24.1],
        "weathercode": [0, 1, 63],
    }
}


def _mock_async_client(*responses: MagicMock) -> AsyncMock:
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.get = AsyncMock(side_effect=list(responses))
    return mock_client


def _json_response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


@pytest.mark.asyncio
async def test_get_weather_returns_structured_forecast() -> None:
    mock_client = _mock_async_client(
        _json_response(GEO_RESPONSE),
        _json_response(FORECAST_RESPONSE),
    )

    with patch("app.tools.weather.httpx.AsyncClient", return_value=mock_client):
        result = await get_weather("Paris", days=3)

    assert result.location == "Paris"
    assert len(result.forecast) == 3
    assert result.forecast[0].date == "2026-07-15"
    assert result.forecast[0].min == "15.2°C"
    assert result.forecast[0].max == "25.4°C"
    assert result.forecast[0].condition == "Clear Sky ☀️"
    assert result.forecast[2].condition == "Rain 🌧"


@pytest.mark.asyncio
async def test_get_weather_raises_when_city_not_found() -> None:
    mock_client = _mock_async_client(_json_response({"results": []}))

    with patch("app.tools.weather.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(CityNotFoundError, match="Paris"):
            await get_weather("Paris")


@pytest.mark.asyncio
async def test_get_weather_clamps_days_between_1_and_14() -> None:
    mock_client = _mock_async_client(
        _json_response(GEO_RESPONSE),
        _json_response(FORECAST_RESPONSE),
    )

    with patch("app.tools.weather.httpx.AsyncClient", return_value=mock_client):
        await get_weather("Paris", days=99)

    forecast_call = mock_client.get.await_args_list[1]
    assert forecast_call.kwargs["params"]["forecast_days"] == 14


@pytest.mark.asyncio
async def test_get_weather_wraps_http_errors() -> None:
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.get = AsyncMock(side_effect=RuntimeError("network down"))

    with patch("app.tools.weather.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(WeatherToolError, match="network down"):
            await get_weather("Paris")


def test_weather_endpoint_returns_forecast() -> None:
    mock_result = WeatherResponse(
        location="Paris",
        forecast=[
            ForecastDay(
                date="2026-07-15",
                min="15.2°C",
                max="25.4°C",
                condition="Clear Sky ☀️",
            )
        ],
    )

    with patch("app.main.get_weather", AsyncMock(return_value=mock_result)):
        response = client.get("/api/v1/weather", params={"city": "Paris", "days": 3})

    assert response.status_code == 200
    body = response.json()
    assert body["location"] == "Paris"
    assert len(body["forecast"]) == 1


def test_weather_endpoint_returns_404_for_unknown_city() -> None:
    with patch(
        "app.main.get_weather",
        AsyncMock(side_effect=CityNotFoundError("Nowhere")),
    ):
        response = client.get("/api/v1/weather", params={"city": "Nowhere"})

    assert response.status_code == 404
    assert response.json()["detail"] == "City 'Nowhere' not found."
