export type TripType = "leisure" | "business";

export type BaggageType = "cabin" | "checked" | "both";

export interface TravelerProfile {
  trip_type: TripType;
  baggage_type: BaggageType;
  activities: string[];
  clothing_preferences: string[];
  medical_or_accessibility_notes?: string[] | null;
  available_items?: string[] | null;
  share_sensitive_notes_with_model: boolean;
}

export interface ChatRequest {
  message: string;
  traveler_profile?: TravelerProfile | null;
}

export interface PackingItem {
  name: string;
  category: string;
  quantity: number;
  reason: string;
  essential: boolean;
}

export interface DailyForecast {
  date: string;
  min: string;
  max: string;
  condition: string;
}

export interface WeatherSummary {
  location: string;
  overview: string;
  min_temperature?: string | null;
  max_temperature?: string | null;
  conditions?: string | null;
  daily_forecast?: DailyForecast[];
}

export interface PackingResponse {
  destination: string;
  start_date: string;
  end_date: string;
  weather_summary: WeatherSummary;
  packing_items: PackingItem[];
  warnings: string[];
  baggage_warnings: string[];
  profile_considerations: string[];
  rules_disclaimer: string;
  language: string;
}

export interface TripFormValues {
  message: string;
  tripType: TripType;
  baggageType: BaggageType | "";
  activities: string;
  clothingPreferences: string;
  availableItems: string;
  medicalNotes: string;
  shareSensitiveNotes: boolean;
}

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export class NetworkError extends Error {
  constructor(message = "Network error while contacting the Packmate API.") {
    super(message);
    this.name = "NetworkError";
  }
}

export class ValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ValidationError";
  }
}

export function parseCommaSeparatedList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function buildChatRequest(values: TripFormValues): ChatRequest {
  const message = values.message.trim();
  if (!message) {
    throw new ValidationError("Travel message is required.");
  }

  if (!values.baggageType) {
    throw new ValidationError("Baggage type is required.");
  }

  const medicalNotes = parseCommaSeparatedList(values.medicalNotes);
  const profile: TravelerProfile = {
    trip_type: values.tripType,
    baggage_type: values.baggageType,
    activities: parseCommaSeparatedList(values.activities),
    clothing_preferences: parseCommaSeparatedList(values.clothingPreferences),
    available_items: parseCommaSeparatedList(values.availableItems),
    share_sensitive_notes_with_model: values.shareSensitiveNotes,
  };

  if (medicalNotes.length > 0) {
    profile.medical_or_accessibility_notes = medicalNotes;
  }

  return {
    message,
    traveler_profile: profile,
  };
}
