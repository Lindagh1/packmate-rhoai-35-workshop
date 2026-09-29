import type { PackingResponse } from "../models/packmate";
import {
  BaggageWarnings,
  ProfileConsiderations,
  RulesDisclaimer,
  WarningList,
} from "./BaggageWarnings";
import { PackingList } from "./PackingList";
import { WeatherSummary } from "./WeatherSummary";

interface PackingResultsProps {
  response: PackingResponse;
}

export function PackingResults({ response }: PackingResultsProps) {
  return (
    <article className="lab-report" aria-label="Packing plan report">
      <h2 className="lab-report-title">
        Packing plan: {response.destination}
      </h2>
      <p className="lab-report-meta">
        {response.start_date} — {response.end_date} · Language: {response.language}
      </p>

      <section className="lab-report-section" aria-labelledby="weather-heading">
        <h3 className="lab-report-section__title" id="weather-heading">
          Weather summary
        </h3>
        <WeatherSummary summary={response.weather_summary} />
      </section>

      {response.warnings.length > 0 && (
        <section className="lab-report-section" aria-labelledby="warnings-heading">
          <h3 className="lab-report-section__title" id="warnings-heading">
            General warnings
          </h3>
          <WarningList warnings={response.warnings} />
        </section>
      )}

      <section className="lab-report-section" aria-labelledby="packing-heading">
        <h3 className="lab-report-section__title" id="packing-heading">
          Packing list
        </h3>
        <PackingList items={response.packing_items} />
      </section>

      {response.baggage_warnings.length > 0 && (
        <section className="lab-report-section" aria-labelledby="baggage-heading">
          <h3 className="lab-report-section__title" id="baggage-heading">
            Baggage guidance
          </h3>
          <BaggageWarnings warnings={response.baggage_warnings} />
        </section>
      )}

      {response.profile_considerations.length > 0 && (
        <section className="lab-report-section" aria-labelledby="profile-heading">
          <h3 className="lab-report-section__title" id="profile-heading">
            Profile considerations
          </h3>
          <ProfileConsiderations items={response.profile_considerations} />
        </section>
      )}

      <section className="lab-report-section" aria-labelledby="disclaimer-heading">
        <h3 className="lab-report-section__title" id="disclaimer-heading">
          Rules disclaimer
        </h3>
        <RulesDisclaimer disclaimer={response.rules_disclaimer} />
      </section>
    </article>
  );
}
