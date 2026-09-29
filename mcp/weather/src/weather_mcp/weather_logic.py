"""Open-Meteo weather fetch logic (shared semantics with Packmate backend)."""

from __future__ import annotations

import httpx
from pydantic import BaseModel, Field

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

WMO_CODES = {
    0: "Clear Sky ☀️",
    1: "Mainly Clear 🌤",
    2: "Partly Cloudy ⛅",
    3: "Overcast ☁️",
    45: "Fog 🌫",
    51: "Drizzle 🌦",
    61: "Slight Rain 🌧",
    63: "Rain 🌧",
    71: "Snow 🌨",
    95: "Thunderstorm ⛈",
}


class CityNotFoundError(Exception):
    def __init__(self, city: str) -> None:
        self.city = city
        super().__init__(f"City '{city}' not found.")


class WeatherToolError(Exception):
    pass


class ForecastDay(BaseModel):
    date: str
    min: str
    max: str
    condition: str


class WeatherResult(BaseModel):
    location: str
    forecast: list[ForecastDay] = Field(default_factory=list)


async def fetch_weather(city: str, days: int = 14) -> WeatherResult:
    """Fetch geocoding and forecast data from Open-Meteo."""
    days_int = min(max(int(days), 1), 14)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            geo_response = await client.get(
                GEOCODING_URL,
                params={"name": city, "count": 1},
            )
            geo_response.raise_for_status()
            geo = geo_response.json()

            if not geo.get("results"):
                raise CityNotFoundError(city)

            loc = geo["results"][0]

            forecast_response = await client.get(
                FORECAST_URL,
                params={
                    "latitude": loc["latitude"],
                    "longitude": loc["longitude"],
                    "daily": "temperature_2m_max,temperature_2m_min,weathercode,precipitation_sum",
                    "timezone": "auto",
                    "forecast_days": days_int,
                },
            )
            forecast_response.raise_for_status()
            daily = forecast_response.json()["daily"]

            forecasts = [
                ForecastDay(
                    date=daily["time"][i],
                    min=f"{daily['temperature_2m_min'][i]}°C",
                    max=f"{daily['temperature_2m_max'][i]}°C",
                    condition=WMO_CODES.get(daily["weathercode"][i], "Variable"),
                )
                for i in range(len(daily["time"]))
            ]

            return WeatherResult(location=loc["name"], forecast=forecasts)
    except CityNotFoundError:
        raise
    except Exception as exc:
        raise WeatherToolError(f"Weather service unavailable: {exc}") from exc
