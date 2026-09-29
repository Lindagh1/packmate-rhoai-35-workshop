import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { BaggageWarnings } from "../components/BaggageWarnings";
import { PackingList } from "../components/PackingList";
import { PackingResults } from "../components/PackingResults";
import { defaultTripFormValues } from "../models/formDefaults";
import { TripForm } from "./TripForm";
import type { PackingResponse } from "../models/packmate";

const sampleResponse: PackingResponse = {
  destination: "Rome",
  start_date: "2026-07-21",
  end_date: "2026-07-23",
  weather_summary: {
    location: "Rome",
    overview: "Warm and sunny.",
    min_temperature: "18°C",
    max_temperature: "30°C",
    conditions: "Clear",
    daily_forecast: [
      {
        date: "2026-07-21",
        min: "18°C",
        max: "29°C",
        condition: "Sunny",
      },
      {
        date: "2026-07-22",
        min: "19°C",
        max: "30°C",
        condition: "Partly cloudy",
      },
    ],
  },
  packing_items: [
    {
      name: "T-shirt",
      category: "Clothing",
      quantity: 3,
      reason: "Hot weather",
      essential: true,
    },
    {
      name: "Sunscreen",
      category: "Toiletries",
      quantity: 1,
      reason: "Strong sun",
      essential: true,
    },
  ],
  warnings: ["Bring sunscreen"],
  baggage_warnings: ["Demo rule: liquids in cabin baggage must be in containers of 100 ml or less."],
  profile_considerations: ["Business trip: include professional attire."],
  rules_disclaimer: "DEMONSTRATION RULES ONLY.",
  language: "fr",
};

describe("TripForm", () => {
  it("renders the trip form fields", () => {
    render(
      <TripForm
        values={defaultTripFormValues}
        onChange={vi.fn()}
        onSubmit={vi.fn()}
        isSubmitting={false}
      />,
    );

    expect(screen.getByLabelText(/Travel message/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Trip type/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Baggage type/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Activities/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Medical or accessibility notes/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("switch")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Generate packing plan/i })).toBeInTheDocument();
  });

  it("does not default baggage type to cabin", () => {
    render(
      <TripForm
        values={defaultTripFormValues}
        onChange={vi.fn()}
        onSubmit={vi.fn()}
        isSubmitting={false}
      />,
    );

    expect(screen.getByLabelText(/Baggage type/i)).toHaveValue("");
  });
});

describe("PackingResults", () => {
  it("displays structured packing response sections", () => {
    render(<PackingResults response={sampleResponse} />);

    expect(screen.getByText(/Packing plan: Rome/i)).toBeInTheDocument();
    expect(screen.getAllByText("Rome").length).toBeGreaterThan(0);
    expect(screen.getByText("Weather summary")).toBeInTheDocument();
    expect(screen.getByText("Packing list")).toBeInTheDocument();
    expect(screen.getByText("Baggage guidance")).toBeInTheDocument();
    expect(screen.getByText(/DEMONSTRATION RULES ONLY/i)).toBeInTheDocument();
  });

  it("shows daily weather forecast rows", () => {
    render(<PackingResults response={sampleResponse} />);

    expect(screen.getByText("2026-07-21")).toBeInTheDocument();
    expect(screen.getByText("2026-07-22")).toBeInTheDocument();
    expect(screen.getByText("Sunny")).toBeInTheDocument();
  });
});

describe("BaggageWarnings", () => {
  it("renders baggage warnings in CAUTION callout", () => {
    render(<BaggageWarnings warnings={sampleResponse.baggage_warnings} />);

    expect(screen.getByText("CAUTION")).toBeInTheDocument();
    expect(screen.getByText(/100 ml or less/i)).toBeInTheDocument();
  });
});

describe("PackingList", () => {
  it("groups items by category", () => {
    render(<PackingList items={sampleResponse.packing_items} />);

    expect(screen.getByText("Clothing")).toBeInTheDocument();
    expect(screen.getByText("Toiletries")).toBeInTheDocument();
    expect(screen.getByText("T-shirt")).toBeInTheDocument();
    expect(screen.getByText("Sunscreen")).toBeInTheDocument();
    expect(screen.getAllByText("Essential").length).toBeGreaterThan(0);
  });
});

describe("sensitive notes storage", () => {
  it("does not persist form values in localStorage", async () => {
    const user = userEvent.setup();
    const setItemSpy = vi.spyOn(Storage.prototype, "setItem");

    render(
      <TripForm
        values={defaultTripFormValues}
        onChange={vi.fn()}
        onSubmit={vi.fn()}
        isSubmitting={false}
      />,
    );

    await user.type(screen.getByLabelText(/Travel message/i), "Trip to Rome");

    expect(setItemSpy).not.toHaveBeenCalled();
    setItemSpy.mockRestore();
  });
});
