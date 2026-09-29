import json
from datetime import date
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.profile import TravelerProfile


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    traveler_profile: TravelerProfile | None = None


class PackingItem(BaseModel):
    name: str
    category: str
    quantity: int = Field(..., ge=1)
    reason: str
    essential: bool


class DailyForecast(BaseModel):
    date: str
    min: str
    max: str
    condition: str


class WeatherSummary(BaseModel):
    location: str
    overview: str
    min_temperature: str | None = None
    max_temperature: str | None = None
    conditions: str | None = None
    daily_forecast: list[DailyForecast] = Field(default_factory=list)

    @field_validator("daily_forecast", mode="before")
    @classmethod
    def coerce_daily_forecast(cls, value: object) -> Any:
        coerced = _coerce_json_value(value)
        if isinstance(coerced, str) and not coerced.strip():
            return []
        return coerced


def _coerce_json_value(value: object) -> object:
    """Decode JSON-encoded strings some models return instead of native objects."""
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


class PackingResponse(BaseModel):
    destination: str
    start_date: date
    end_date: date
    weather_summary: WeatherSummary
    packing_items: list[PackingItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    baggage_warnings: list[str] = Field(default_factory=list)
    profile_considerations: list[str] = Field(default_factory=list)
    rules_disclaimer: str
    language: str

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def parse_iso_date(cls, value: object) -> object:
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            return date.fromisoformat(value)
        return value

    @field_validator(
        "packing_items",
        "warnings",
        "baggage_warnings",
        "profile_considerations",
        mode="before",
    )
    @classmethod
    def coerce_list_fields(cls, value: object) -> Any:
        coerced = _coerce_json_value(value)
        if isinstance(coerced, str) and not coerced.strip():
            return []
        return coerced

    @field_validator("weather_summary", mode="before")
    @classmethod
    def coerce_weather_summary(cls, value: object) -> Any:
        return _coerce_json_value(value)

    @model_validator(mode="after")
    def validate_date_order(self) -> "PackingResponse":
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot be earlier than start_date")
        return self
