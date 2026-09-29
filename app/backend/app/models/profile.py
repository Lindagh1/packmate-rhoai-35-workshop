from typing import Literal

from pydantic import BaseModel, Field

_MEDICAL_KEYWORDS = (
    "medication",
    "medicine",
    "prescription",
    "insulin",
    "syringe",
    "inhaler",
    "medical",
    "diabetes",
)
_ACCESSIBILITY_KEYWORDS = (
    "wheelchair",
    "mobility",
    "accessibility",
    "accessible",
    "vision",
    "hearing",
    "assistance",
    "mobility aid",
)


class TravelerProfile(BaseModel):
    trip_type: Literal["leisure", "business"]
    baggage_type: Literal["cabin", "checked", "both"]
    activities: list[str] = Field(default_factory=list)
    clothing_preferences: list[str] = Field(default_factory=list)
    medical_or_accessibility_notes: list[str] | None = None
    available_items: list[str] | None = None
    share_sensitive_notes_with_model: bool = Field(
        default=False,
        description=(
            "When true, medical_or_accessibility_notes are transmitted to the LLM "
            "provider for tailoring recommendations. Notes are never logged. "
            "Default is false."
        ),
    )

    def has_sensitive_notes(self) -> bool:
        return bool(self.medical_or_accessibility_notes)

    def medical_planning_required(self) -> bool:
        if not self.medical_or_accessibility_notes:
            return False
        text = " ".join(self.medical_or_accessibility_notes).lower()
        return any(keyword in text for keyword in _MEDICAL_KEYWORDS)

    def accessibility_planning_required(self) -> bool:
        if not self.medical_or_accessibility_notes:
            return False
        text = " ".join(self.medical_or_accessibility_notes).lower()
        return any(keyword in text for keyword in _ACCESSIBILITY_KEYWORDS)

    def derive_sensitive_considerations(self) -> list[str]:
        """Generic considerations derived locally without exposing note content."""
        considerations: list[str] = []

        if self.medical_planning_required():
            considerations.append(
                "Verify medication transport and storage requirements before departure."
            )

        if self.accessibility_planning_required():
            considerations.append(
                "Verify accessibility and mobility assistance requirements with the airline."
            )

        if (
            self.has_sensitive_notes()
            and not self.medical_planning_required()
            and not self.accessibility_planning_required()
        ):
            considerations.append(
                "Review medical and accessibility travel requirements with the airline before departure."
            )

        return considerations

    def for_logging(self) -> dict:
        """Safe profile payload without sensitive medical notes."""
        data = {
            "trip_type": self.trip_type,
            "baggage_type": self.baggage_type,
            "activities": self.activities,
            "clothing_preferences": self.clothing_preferences,
            "available_items": self.available_items,
            "share_sensitive_notes_with_model": self.share_sensitive_notes_with_model,
            "medical_planning_required": self.medical_planning_required(),
            "accessibility_planning_required": self.accessibility_planning_required(),
            "has_medical_or_accessibility_notes": self.has_sensitive_notes(),
        }
        return data

    def for_llm(self) -> dict:
        """Profile payload safe for prompts and tool results by default."""
        payload = {
            "trip_type": self.trip_type,
            "baggage_type": self.baggage_type,
            "activities": self.activities,
            "clothing_preferences": self.clothing_preferences,
            "available_items": self.available_items,
            "medical_planning_required": self.medical_planning_required(),
            "accessibility_planning_required": self.accessibility_planning_required(),
            "share_sensitive_notes_with_model": self.share_sensitive_notes_with_model,
        }

        if self.share_sensitive_notes_with_model and self.medical_or_accessibility_notes:
            payload["medical_or_accessibility_notes"] = self.medical_or_accessibility_notes
            payload["sensitive_notes_shared_with_model"] = True

        return payload

    def for_agent(self) -> dict:
        """Backward-compatible alias for LLM-safe profile representation."""
        return self.for_llm()
