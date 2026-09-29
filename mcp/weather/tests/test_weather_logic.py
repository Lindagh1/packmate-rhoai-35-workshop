import pytest

from weather_mcp.weather_logic import CityNotFoundError, WeatherResult, fetch_weather


@pytest.mark.asyncio
async def test_fetch_weather_city_not_found(monkeypatch):
    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params=None):
            class Resp:
                def raise_for_status(self):
                    return None

                def json(self):
                    return {"results": []}

            return Resp()

    monkeypatch.setattr("weather_mcp.weather_logic.httpx.AsyncClient", lambda **kw: FakeClient())

    with pytest.raises(CityNotFoundError):
        await fetch_weather("NowhereCityXYZ")


@pytest.mark.asyncio
async def test_fetch_weather_success(monkeypatch):
    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params=None):
            class Resp:
                def __init__(self, payload):
                    self._payload = payload

                def raise_for_status(self):
                    return None

                def json(self):
                    return self._payload

            if "geocoding" in url:
                return Resp(
                    {
                        "results": [
                            {"name": "Rome", "latitude": 41.9, "longitude": 12.5}
                        ]
                    }
                )
            return Resp(
                {
                    "daily": {
                        "time": ["2026-07-16"],
                        "temperature_2m_min": [18.0],
                        "temperature_2m_max": [28.0],
                        "weathercode": [0],
                    }
                }
            )

    monkeypatch.setattr("weather_mcp.weather_logic.httpx.AsyncClient", lambda **kw: FakeClient())
    result = await fetch_weather("Rome", days=1)
    assert isinstance(result, WeatherResult)
    assert result.location == "Rome"
    assert len(result.forecast) == 1
    assert result.forecast[0].max == "28.0°C"
