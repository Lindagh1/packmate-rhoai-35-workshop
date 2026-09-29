import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from app.models.baggage import BaggageRulesResult
from app.models.profile import TravelerProfile

BAGGAGE_RULES_PATH = Path(__file__).resolve().parent.parent / "data" / "baggage_rules.json"

BaggageType = Literal["cabin", "checked", "both", "unknown"]

_LIQUID_VOLUME_PATTERN = re.compile(r"(\d+)\s*ml", re.IGNORECASE)


@lru_cache(maxsize=1)
def load_baggage_rules() -> dict:
    with BAGGAGE_RULES_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def get_rules_disclaimer() -> str:
    return load_baggage_rules()["disclaimer"]


def resolve_baggage_type(profile: TravelerProfile | None) -> BaggageType:
    if profile is None:
        return "unknown"
    return profile.baggage_type


def _normalize(value: str | None) -> str:
    return (value or "").strip().lower()


def _matches_baggage_type(rule_types: list[str], baggage_type: BaggageType) -> bool:
    if baggage_type == "unknown":
        return False
    if baggage_type in rule_types:
        return True
    if baggage_type == "both":
        return "cabin" in rule_types or "checked" in rule_types
    return False


def _matches_keywords(text: str, keywords: list[str]) -> bool:
    if not text:
        return False
    return any(keyword in text for keyword in keywords)


def _liquid_over_100ml_warnings(item: str, baggage_type: BaggageType) -> list[str]:
    if baggage_type not in {"cabin", "both"}:
        return []

    warnings: list[str] = []
    for match in _LIQUID_VOLUME_PATTERN.finditer(item):
        if int(match.group(1)) > 100:
            warnings.append(
                "Demo rule: liquid containers above 100 ml are generally not permitted "
                "in cabin baggage unless medically required and documented."
            )
            break
    return warnings


def _rule_warnings_for_baggage_type(rule: dict, baggage_type: BaggageType) -> list[str]:
    if baggage_type == "unknown":
        return list(rule.get("unknown_warnings", []))

    warnings = list(rule.get("warnings", []))
    if baggage_type == "both":
        return warnings

    return warnings


def lookup_baggage_rules(
    baggage_type: BaggageType,
    item: str | None = None,
    category: str | None = None,
    include_general_rules: bool = False,
) -> BaggageRulesResult:
    rules_data = load_baggage_rules()
    normalized_item = _normalize(item)
    normalized_category = _normalize(category)
    search_text = " ".join(part for part in [normalized_item, normalized_category] if part)

    warnings: list[str] = []
    matched_rule_ids: list[str] = []

    for rule in rules_data["rules"]:
        if baggage_type == "unknown":
            if not rule.get("unknown_warnings"):
                continue
        elif not _matches_baggage_type(rule["baggage_types"], baggage_type):
            continue

        category_match = _matches_keywords(normalized_category, rule.get("categories", []))
        keyword_match = _matches_keywords(search_text, rule.get("keywords", []))

        if category_match or keyword_match:
            matched_rule_ids.append(rule["id"])
            for warning in _rule_warnings_for_baggage_type(rule, baggage_type):
                if warning not in warnings:
                    warnings.append(warning)

    for warning in _liquid_over_100ml_warnings(normalized_item, baggage_type):
        if warning not in warnings:
            warnings.append(warning)
            if "liquids_over_100ml_cabin" not in matched_rule_ids:
                matched_rule_ids.append("liquids_over_100ml_cabin")

    general_rules: list[str] = []
    if include_general_rules and baggage_type != "unknown":
        general_rules = list(rules_data.get("general_rules", []))
        limits = rules_data.get("general_limits", {})
        if limits:
            if baggage_type == "cabin":
                general_rules.insert(
                    0,
                    "Demo rule: typical generic limits are "
                    f"cabin {limits.get('cabin_weight_kg')} kg ({limits.get('cabin_dimensions_cm')}).",
                )
            elif baggage_type == "checked":
                general_rules.insert(
                    0,
                    "Demo rule: typical generic limits are "
                    f"checked {limits.get('checked_weight_kg')} kg ({limits.get('checked_dimensions_cm')}).",
                )
            else:
                general_rules.insert(
                    0,
                    "Demo rule: typical generic limits are "
                    f"cabin {limits.get('cabin_weight_kg')} kg ({limits.get('cabin_dimensions_cm')}), "
                    f"checked {limits.get('checked_weight_kg')} kg ({limits.get('checked_dimensions_cm')}).",
                )

    return BaggageRulesResult(
        warnings=warnings,
        matched_rule_ids=matched_rule_ids,
        general_rules=general_rules,
        disclaimer=rules_data["disclaimer"],
    )
