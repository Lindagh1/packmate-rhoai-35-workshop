from app.models.profile import TravelerProfile
from app.tools.traveler_profile import lookup_traveler_profile


def test_business_profile_considerations() -> None:
    profile = TravelerProfile(
        trip_type="business",
        baggage_type="cabin",
        activities=["client meetings"],
        clothing_preferences=["formal"],
    )

    result = lookup_traveler_profile(profile)

    assert result["available"] is True
    assert result["trip_type"] == "business"
    assert any("business" in item.lower() for item in result["considerations"])


def test_leisure_profile_with_activities() -> None:
    profile = TravelerProfile(
        trip_type="leisure",
        baggage_type="both",
        activities=["hiking", "swimming"],
        clothing_preferences=["sportswear"],
        available_items=["running shoes"],
    )

    result = lookup_traveler_profile(profile)

    assert result["available"] is True
    assert "hiking" in result["considerations"][1]
    assert any("running shoes" in item for item in result["considerations"])


def test_absent_profile_returns_unavailable() -> None:
    result = lookup_traveler_profile(None)

    assert result["available"] is False
    assert "No traveler profile" in result["message"]


def test_profile_for_logging_hides_medical_notes() -> None:
    profile = TravelerProfile(
        trip_type="leisure",
        baggage_type="cabin",
        activities=["walking"],
        clothing_preferences=["casual"],
        medical_or_accessibility_notes=["Requires wheelchair assistance"],
    )

    logged = profile.for_logging()

    assert "medical_or_accessibility_notes" not in logged
    assert logged["accessibility_planning_required"] is True
    assert "wheelchair" not in str(logged)


def test_profile_for_llm_excludes_medical_notes_by_default() -> None:
    profile = TravelerProfile(
        trip_type="leisure",
        baggage_type="cabin",
        activities=["walking"],
        clothing_preferences=["casual"],
        medical_or_accessibility_notes=["Requires insulin refrigeration"],
    )

    llm_view = profile.for_llm()

    assert "medical_or_accessibility_notes" not in llm_view
    assert llm_view["medical_planning_required"] is True
    assert llm_view["share_sensitive_notes_with_model"] is False


def test_traveler_profile_tool_excludes_medical_notes_by_default() -> None:
    profile = TravelerProfile(
        trip_type="leisure",
        baggage_type="cabin",
        activities=["walking"],
        clothing_preferences=["casual"],
        medical_or_accessibility_notes=["Requires insulin refrigeration"],
    )

    result = lookup_traveler_profile(profile)

    assert "medical_or_accessibility_notes" not in result
    assert result["medical_planning_required"] is True
    assert "insulin" not in str(result)


def test_profile_for_llm_includes_notes_when_explicitly_shared() -> None:
    profile = TravelerProfile(
        trip_type="leisure",
        baggage_type="cabin",
        activities=["walking"],
        clothing_preferences=["casual"],
        medical_or_accessibility_notes=["Requires insulin refrigeration"],
        share_sensitive_notes_with_model=True,
    )

    llm_view = profile.for_llm()

    assert llm_view["share_sensitive_notes_with_model"] is True
    assert llm_view["sensitive_notes_shared_with_model"] is True
    assert llm_view["medical_or_accessibility_notes"] == ["Requires insulin refrigeration"]


def test_profile_for_logging_never_includes_notes_even_when_shared() -> None:
    profile = TravelerProfile(
        trip_type="leisure",
        baggage_type="cabin",
        activities=["walking"],
        clothing_preferences=["casual"],
        medical_or_accessibility_notes=["Requires insulin refrigeration"],
        share_sensitive_notes_with_model=True,
    )

    logged = profile.for_logging()

    assert "medical_or_accessibility_notes" not in logged
    assert "insulin" not in str(logged)


def test_derive_sensitive_considerations_uses_generic_wording() -> None:
    profile = TravelerProfile(
        trip_type="leisure",
        baggage_type="cabin",
        activities=["walking"],
        clothing_preferences=["casual"],
        medical_or_accessibility_notes=["Requires insulin refrigeration"],
    )

    considerations = profile.derive_sensitive_considerations()

    assert any("medication transport" in item.lower() for item in considerations)
    assert "insulin" not in " ".join(considerations).lower()
