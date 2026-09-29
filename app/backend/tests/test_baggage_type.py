import pytest

from app.agent.enrichment import (
    baggage_type_precision_warning,
    collect_packing_item_warnings,
    enrich_packing_response,
)
from app.models.chat import PackingItem, PackingResponse, WeatherSummary
from app.models.profile import TravelerProfile
from app.tools.baggage import load_baggage_rules, lookup_baggage_rules, resolve_baggage_type

RULES_DISCLAIMER = load_baggage_rules()["disclaimer"]


@pytest.fixture(autouse=True)
def clear_rules_cache() -> None:
    load_baggage_rules.cache_clear()
    yield
    load_baggage_rules.cache_clear()


def _response(language: str = "fr", packing_items: list[PackingItem] | None = None) -> PackingResponse:
    return PackingResponse(
        destination="Rome",
        start_date="2026-07-21",
        end_date="2026-07-23",
        weather_summary=WeatherSummary(location="Rome", overview="Warm."),
        packing_items=packing_items or [],
        warnings=[],
        baggage_warnings=[],
        profile_considerations=[],
        rules_disclaimer=RULES_DISCLAIMER,
        language=language,
    )


def test_resolve_baggage_type_unknown_when_profile_absent() -> None:
    assert resolve_baggage_type(None) == "unknown"


def test_resolve_baggage_type_uses_profile_value_when_present() -> None:
    profile = TravelerProfile(
        trip_type="business",
        baggage_type="checked",
        activities=["meetings"],
        clothing_preferences=["formal"],
    )

    assert resolve_baggage_type(profile) == "checked"


def test_unknown_baggage_type_does_not_apply_cabin_liquid_rules() -> None:
    result = lookup_baggage_rules(
        baggage_type="unknown",
        item="shampoo 200ml",
        category="liquids",
    )

    assert result.warnings == []
    assert "liquids_over_100ml_cabin" not in result.matched_rule_ids


def test_unknown_baggage_type_still_flags_external_battery_generically() -> None:
    result = lookup_baggage_rules(
        baggage_type="unknown",
        item="power bank",
        category="electronics",
    )

    assert "external_batteries" in result.matched_rule_ids
    assert any("confirm allowed placement" in warning.lower() for warning in result.warnings)
    assert "cabin baggage, not checked baggage" not in " ".join(result.warnings)


def test_cabin_applies_cabin_liquid_rules() -> None:
    result = lookup_baggage_rules(
        baggage_type="cabin",
        item="shampoo 200ml",
        category="liquids",
    )

    assert "liquids_over_100ml_cabin" in result.matched_rule_ids


def test_checked_does_not_apply_cabin_liquid_over_100ml_rule() -> None:
    result = lookup_baggage_rules(
        baggage_type="checked",
        item="shampoo 200ml",
        category="liquids",
    )

    assert "liquids_over_100ml_cabin" not in result.matched_rule_ids


def test_both_applies_cabin_and_checked_rule_sets() -> None:
    cabin_only = lookup_baggage_rules(
        baggage_type="cabin",
        item="kitchen knife",
        category="sharp_objects",
    )
    both_result = lookup_baggage_rules(
        baggage_type="both",
        item="kitchen knife",
        category="sharp_objects",
    )

    assert cabin_only.warnings
    assert both_result.warnings == cabin_only.warnings


def test_precision_warning_in_french_when_language_is_fr() -> None:
    enriched = enrich_packing_response(
        response=_response(language="fr"),
        profile=None,
        collected_baggage_warnings=[],
        rules_disclaimer=RULES_DISCLAIMER,
    )

    assert any("Précisez si vous voyagez" in warning for warning in enriched.warnings)


def test_precision_warning_in_english_when_language_is_en() -> None:
    enriched = enrich_packing_response(
        response=_response(language="en"),
        profile=None,
        collected_baggage_warnings=[],
        rules_disclaimer=RULES_DISCLAIMER,
    )

    assert any("Specify whether you are travelling" in warning for warning in enriched.warnings)


def test_absent_profile_does_not_add_cabin_specific_item_warnings() -> None:
    warnings = collect_packing_item_warnings(
        [
            PackingItem(
                name="shampoo 200ml",
                category="liquids",
                quantity=1,
                reason="Hygiene",
                essential=False,
            )
        ],
        baggage_type="unknown",
    )

    assert warnings == []


def test_absent_profile_still_flags_battery_without_cabin_assumption() -> None:
    warnings = collect_packing_item_warnings(
        [
            PackingItem(
                name="power bank",
                category="electronics",
                quantity=1,
                reason="Charge devices",
                essential=True,
            )
        ],
        baggage_type="unknown",
    )

    assert any("confirm allowed placement" in warning.lower() for warning in warnings)


def test_profile_present_does_not_add_precision_warning() -> None:
    profile = TravelerProfile(
        trip_type="leisure",
        baggage_type="cabin",
        activities=["walking"],
        clothing_preferences=["casual"],
    )

    enriched = enrich_packing_response(
        response=_response(language="fr"),
        profile=profile,
        collected_baggage_warnings=[],
        rules_disclaimer=RULES_DISCLAIMER,
    )

    assert not any("Précisez si vous voyagez" in warning for warning in enriched.warnings)


def test_baggage_type_precision_warning_helpers() -> None:
    assert "Précisez" in baggage_type_precision_warning("fr")
    assert "Specify whether" in baggage_type_precision_warning("en")
