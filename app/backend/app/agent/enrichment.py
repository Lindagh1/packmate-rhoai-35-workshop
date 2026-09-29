from datetime import date

from app.models.chat import DailyForecast, PackingItem, PackingResponse, WeatherSummary
from app.models.profile import TravelerProfile
from app.models.weather import WeatherResponse
from app.tools.baggage import (
    BaggageType,
    get_rules_disclaimer,
    lookup_baggage_rules,
    resolve_baggage_type,
)

# Preferred packing categories (EN / FR aliases → canonical label).
_CATEGORY_CANONICAL: list[tuple[str, tuple[str, ...]]] = [
    ("Clothing", ("clothing", "clothes", "vêtements", "vetements", "habits", "apparel")),
    (
        "Swimwear",
        ("swimwear", "swim", "maillot", "beachwear", "swimsuit", "bikini"),
    ),
    (
        "Footwear",
        ("footwear", "shoes", "chaussures", "sneakers", "boots"),
    ),
    (
        "Toiletries",
        (
            "toiletries",
            "toilette",
            "hygiene",
            "hygiène",
            "sun care",
            "sunscreen",
            "protection solaire",
            "cosmetics",
        ),
    ),
    ("Documents", ("documents", "papers", "papiers", "travel documents")),
    (
        "Electronics",
        ("electronics", "électronique", "electronique", "tech", "chargers"),
    ),
    (
        "Accessories",
        ("accessories", "accessoires", "hat", "bag", "sac"),
    ),
    ("Essentials", ("essentials", "essentiels", "misc", "other", "divers")),
]


def merge_stable_unique(*sources: list[str]) -> list[str]:
    merged: list[str] = []
    for source in sources:
        for value in source:
            if value not in merged:
                merged.append(value)
    return merged


def baggage_type_precision_warning(language: str) -> str:
    if language.lower().startswith("fr"):
        return (
            "Précisez si vous voyagez avec un bagage cabine, un bagage en soute "
            "ou les deux pour valider les restrictions bagages."
        )
    return (
        "Specify whether you are travelling with cabin baggage, checked baggage, "
        "or both to validate baggage restrictions."
    )


def collect_profile_baggage_warnings(profile: TravelerProfile) -> list[str]:
    """Apply baggage demo rules when a profile with an explicit baggage_type is provided."""
    result = lookup_baggage_rules(
        baggage_type=profile.baggage_type,
        include_general_rules=True,
    )
    return merge_stable_unique(result.warnings, result.general_rules)


def collect_packing_item_warnings(
    packing_items: list[PackingItem],
    baggage_type: BaggageType,
) -> list[str]:
    """Analyze packing items deterministically against baggage demo rules."""
    warnings: list[str] = []

    for item in packing_items:
        result = lookup_baggage_rules(
            baggage_type=baggage_type,
            item=item.name,
            category=item.category,
        )
        warnings = merge_stable_unique(warnings, result.warnings)

    return warnings


def filter_sensitive_note_leaks(
    values: list[str],
    profile: TravelerProfile | None,
) -> list[str]:
    if profile is None or not profile.medical_or_accessibility_notes:
        return values

    note_fragments = {note.strip().lower() for note in profile.medical_or_accessibility_notes if note.strip()}
    filtered: list[str] = []

    for value in values:
        normalized = value.strip().lower()
        if any(fragment in normalized or normalized in fragment for fragment in note_fragments):
            continue
        filtered.append(value)

    return filtered


def normalize_packing_category(category: str) -> str:
    normalized = category.strip().lower()
    for canonical, aliases in _CATEGORY_CANONICAL:
        if normalized == canonical.lower() or any(alias in normalized for alias in aliases):
            return canonical
    return category.strip() or "Essentials"


def organize_packing_items(items: list[PackingItem]) -> list[PackingItem]:
    """Normalize categories and sort into a coherent packing order."""
    order = {name: index for index, (name, _) in enumerate(_CATEGORY_CANONICAL)}
    organized = [
        item.model_copy(update={"category": normalize_packing_category(item.category)})
        for item in items
    ]
    return sorted(
        organized,
        key=lambda item: (
            order.get(item.category, len(order)),
            0 if item.essential else 1,
            item.name.lower(),
        ),
    )


def build_daily_forecast(
    weather: WeatherResponse,
    start: date,
    end: date,
) -> list[DailyForecast]:
    days: list[DailyForecast] = []
    for day in weather.forecast:
        try:
            day_date = date.fromisoformat(day.date)
        except ValueError:
            continue
        if start <= day_date <= end:
            days.append(
                DailyForecast(
                    date=day.date,
                    min=day.min,
                    max=day.max,
                    condition=day.condition,
                )
            )
    if days:
        return days
    # Fallback: keep tool forecast as-is when dates do not overlap.
    return [
        DailyForecast(
            date=day.date,
            min=day.min,
            max=day.max,
            condition=day.condition,
        )
        for day in weather.forecast
    ]


def merge_weather_summary(
    summary: WeatherSummary,
    weather: WeatherResponse | None,
    start: date,
    end: date,
) -> WeatherSummary:
    if weather is None:
        return summary

    daily = build_daily_forecast(weather, start, end)
    mins = [day.min for day in daily if day.min]
    maxs = [day.max for day in daily if day.max]
    conditions = [day.condition for day in daily if day.condition]

    return summary.model_copy(
        update={
            "location": summary.location or weather.location,
            "min_temperature": summary.min_temperature or (mins[0] if mins else None),
            "max_temperature": summary.max_temperature or (maxs[-1] if maxs else None),
            "conditions": summary.conditions or (", ".join(dict.fromkeys(conditions)) if conditions else None),
            "daily_forecast": daily or summary.daily_forecast,
        }
    )


def enrich_packing_response(
    response: PackingResponse,
    profile: TravelerProfile | None,
    collected_baggage_warnings: list[str],
    rules_disclaimer: str | None,
    weather_response: WeatherResponse | None = None,
) -> PackingResponse:
    baggage_type = resolve_baggage_type(profile)
    organized_items = organize_packing_items(response.packing_items)

    deterministic_baggage_warnings = merge_stable_unique(
        collected_baggage_warnings,
        collect_packing_item_warnings(organized_items, baggage_type),
    )

    deterministic_general_warnings: list[str] = []
    if baggage_type == "unknown":
        deterministic_general_warnings.append(
            baggage_type_precision_warning(response.language)
        )

    deterministic_profile_considerations = profile.derive_sensitive_considerations() if profile else []
    safe_profile_considerations = filter_sensitive_note_leaks(
        response.profile_considerations,
        profile,
    )

    weather_summary = merge_weather_summary(
        response.weather_summary,
        weather_response,
        response.start_date,
        response.end_date,
    )

    return response.model_copy(
        update={
            "packing_items": organized_items,
            "weather_summary": weather_summary,
            "baggage_warnings": deterministic_baggage_warnings,
            "profile_considerations": merge_stable_unique(
                deterministic_profile_considerations,
                safe_profile_considerations,
            ),
            "warnings": merge_stable_unique(
                filter_sensitive_note_leaks(response.warnings, profile),
                deterministic_general_warnings,
            ),
            "rules_disclaimer": rules_disclaimer or response.rules_disclaimer or get_rules_disclaimer(),
        }
    )
