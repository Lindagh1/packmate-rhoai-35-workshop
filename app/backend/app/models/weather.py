from pydantic import BaseModel, Field


class ForecastDay(BaseModel):
    date: str
    min: str
    max: str
    condition: str


class WeatherResponse(BaseModel):
    location: str
    forecast: list[ForecastDay] = Field(default_factory=list)
