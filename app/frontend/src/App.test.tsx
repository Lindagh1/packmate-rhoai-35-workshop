import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { postChatStream } from "./api/packmateApi";
import { LAB_STEPS } from "./components/LabShell";
import { ApiError, type PackingResponse } from "./models/packmate";

vi.mock("./api/packmateApi", async () => {
  const actual = await vi.importActual<typeof import("./api/packmateApi")>("./api/packmateApi");
  return {
    ...actual,
    postChatStream: vi.fn(),
  };
});

const mockedPostChatStream = vi.mocked(postChatStream);

const sampleResponse: PackingResponse = {
  destination: "Rome",
  start_date: "2026-07-21",
  end_date: "2026-07-23",
  weather_summary: {
    location: "Rome",
    overview: "Warm.",
  },
  packing_items: [],
  warnings: [],
  baggage_warnings: ["Demo baggage warning"],
  profile_considerations: [],
  rules_disclaimer: "DEMO",
  language: "fr",
};

describe("App", () => {
  beforeEach(() => {
    mockedPostChatStream.mockReset();
  });

  it("renders the lab header and navigation steps", () => {
    render(<App />);

    expect(screen.getByText("Red Hat | Packmate Lab")).toBeInTheDocument();
    expect(screen.getByText("AI-powered travel preparation")).toBeInTheDocument();
    expect(screen.getByText("Create your packing plan")).toBeInTheDocument();

    for (const step of LAB_STEPS) {
      expect(screen.getByText(step.label)).toBeInTheDocument();
    }
  });

  it("shows a loading state while waiting for the backend", async () => {
    mockedPostChatStream.mockImplementation(
      (_request, options) =>
        new Promise((resolve) => {
          options?.onProgress?.("weather");
          setTimeout(() => resolve(sampleResponse), 100);
        }),
    );

    const user = userEvent.setup();
    render(<App />);

    await user.type(
      screen.getByLabelText(/Travel message/i),
      "Je pars à Rome la semaine prochaine",
    );
    await user.selectOptions(screen.getByLabelText(/Baggage type/i), "cabin");
    await user.click(screen.getByRole("button", { name: /Generate packing plan/i }));

    expect(screen.getByText(/Checking weather/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Cancel request/i })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText(/Packing plan: Rome/i)).toBeInTheDocument();
    });
  });

  it("displays backend errors with retry", async () => {
    mockedPostChatStream.mockRejectedValue(new ApiError(503, "LLM is not configured."));

    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByLabelText(/Travel message/i), "Trip to Rome");
    await user.selectOptions(screen.getByLabelText(/Baggage type/i), "cabin");
    await user.click(screen.getByRole("button", { name: /Generate packing plan/i }));

    expect(await screen.findByText(/LLM is not configured/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Try again/i })).toBeInTheDocument();
  });

  it("shows validation error when baggage type is missing", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByLabelText(/Travel message/i), "Trip to Rome");
    await user.click(screen.getByRole("button", { name: /Generate packing plan/i }));

    expect(await screen.findByText(/Baggage type is required/i)).toBeInTheDocument();
    expect(mockedPostChatStream).not.toHaveBeenCalled();
  });
});
