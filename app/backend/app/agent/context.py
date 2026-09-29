from dataclasses import dataclass, field

from app.agent.enrichment import collect_profile_baggage_warnings, merge_stable_unique
from app.models.profile import TravelerProfile
from app.models.weather import WeatherResponse
from app.tools.baggage import get_rules_disclaimer


@dataclass
class ToolContext:
    traveler_profile: TravelerProfile | None = None
    collected_baggage_warnings: list[str] = field(default_factory=list)
    rules_disclaimer: str | None = None
    weather_response: WeatherResponse | None = None

    def __post_init__(self) -> None:
        self.apply_deterministic_profile_baggage_rules()

    def apply_deterministic_profile_baggage_rules(self) -> None:
        if self.traveler_profile is None:
            return

        warnings = collect_profile_baggage_warnings(self.traveler_profile)
        self.record_baggage_result(warnings, get_rules_disclaimer())

    def record_baggage_result(self, warnings: list[str], disclaimer: str) -> None:
        self.collected_baggage_warnings = merge_stable_unique(
            self.collected_baggage_warnings,
            warnings,
        )
        self.rules_disclaimer = disclaimer

    def record_weather_result(self, weather: WeatherResponse) -> None:
        self.weather_response = weather
