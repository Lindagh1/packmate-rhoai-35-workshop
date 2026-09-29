import type { WeatherSummary as WeatherSummaryModel } from "../models/packmate";

interface WeatherSummaryProps {
  summary: WeatherSummaryModel;
}

export function WeatherSummary({ summary }: WeatherSummaryProps) {
  const daily = summary.daily_forecast ?? [];

  return (
    <div className="lab-weather">
      <dl className="lab-weather-grid">
        <div>
          <dt>Location</dt>
          <dd>{summary.location}</dd>
        </div>
        <div>
          <dt>Overview</dt>
          <dd>{summary.overview}</dd>
        </div>
        {summary.min_temperature && (
          <div>
            <dt>Min temperature</dt>
            <dd>{summary.min_temperature}</dd>
          </div>
        )}
        {summary.max_temperature && (
          <div>
            <dt>Max temperature</dt>
            <dd>{summary.max_temperature}</dd>
          </div>
        )}
        {summary.conditions && (
          <div>
            <dt>Conditions</dt>
            <dd>{summary.conditions}</dd>
          </div>
        )}
      </dl>

      {daily.length > 0 && (
        <div className="lab-table-wrap lab-weather-daily">
          <table className="lab-table" aria-label="Daily weather forecast">
            <thead>
              <tr>
                <th scope="col">Date</th>
                <th scope="col">Min</th>
                <th scope="col">Max</th>
                <th scope="col">Conditions</th>
              </tr>
            </thead>
            <tbody>
              {daily.map((day) => (
                <tr key={day.date}>
                  <td data-label="Date">{day.date}</td>
                  <td data-label="Min">{day.min}</td>
                  <td data-label="Max">{day.max}</td>
                  <td data-label="Conditions">{day.condition}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
