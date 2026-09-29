import { describe, expect, it } from "vitest";
import { defaultTripFormValues } from "../models/formDefaults";
import {
  buildChatRequest,
  ValidationError,
  type TripFormValues,
} from "./packmate";

const validValues: TripFormValues = {
  ...defaultTripFormValues,
  message: "Je pars à Rome la semaine prochaine",
  baggageType: "cabin",
  activities: "museums, walking",
  clothingPreferences: "casual",
  availableItems: "running shoes",
  medicalNotes: "Requires insulin refrigeration",
};

describe("buildChatRequest", () => {
  it("requires a travel message", () => {
    expect(() =>
      buildChatRequest({ ...validValues, message: "   " }),
    ).toThrow(ValidationError);
  });

  it("requires an explicit baggage type", () => {
    expect(() =>
      buildChatRequest({ ...validValues, baggageType: "" }),
    ).toThrow("Baggage type is required.");
  });

  it("builds the expected ChatRequest payload", () => {
    const request = buildChatRequest({
      ...validValues,
      shareSensitiveNotes: true,
    });

    expect(request).toEqual({
      message: "Je pars à Rome la semaine prochaine",
      traveler_profile: {
        trip_type: "leisure",
        baggage_type: "cabin",
        activities: ["museums", "walking"],
        clothing_preferences: ["casual"],
        available_items: ["running shoes"],
        medical_or_accessibility_notes: ["Requires insulin refrigeration"],
        share_sensitive_notes_with_model: true,
      },
    });
  });

  it("omits medical notes when the field is empty", () => {
    const request = buildChatRequest({
      ...validValues,
      medicalNotes: "",
      shareSensitiveNotes: false,
    });

    expect(request.traveler_profile?.medical_or_accessibility_notes).toBeUndefined();
    expect(request.traveler_profile?.share_sensitive_notes_with_model).toBe(false);
  });
});
