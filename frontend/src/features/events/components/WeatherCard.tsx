import type { ReactNode } from 'react';
import { Card } from '../../../components/ui/Card';
import { EmptyState } from '../../../components/ui/EmptyState';
import {
  formatPercent,
  formatPrecip,
  formatPressure,
  formatTemp,
  formatWind,
} from '../../../lib/format';
import type { EventWeather } from '../api';
import { eventExplainers } from '../explainers';
import { About } from './About';

const CONDITION_LABELS: Record<string, string> = {
  rain: 'Rain',
  windy: 'Windy',
  overcast: 'Overcast',
  partly_cloudy: 'Partly cloudy',
  clear: 'Clear',
};

const POINTS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'] as const;

export function compass(deg: number): string {
  const normalized = ((deg % 360) + 360) % 360;
  // Index is always 0..7; the cast keeps this valid under noUncheckedIndexedAccess.
  return POINTS[Math.round(normalized / 45) % 8] as (typeof POINTS)[number];
}

function windText(w: EventWeather): string {
  const direction = w.wind_dir_deg === null ? '' : ` ${compass(w.wind_dir_deg)}`;
  return `${formatWind(w.wind_mph)}${direction}, gusts ${formatWind(w.gust_mph)}`;
}

function Item({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-text-muted">{label}</dt>
      <dd className="tabular-nums">{value}</dd>
    </div>
  );
}

/** The event-window weather (C7: 10:00–12:00 local), in °F, mph, inches and inHg. */
export function WeatherCard({ weather }: { weather: EventWeather | null }) {
  return (
    <Card title="Weather (10:00–12:00)">
      {weather === null ? (
        <EmptyState title="No weather recorded for this Sunday" />
      ) : (
        <>
          <About explainer={eventExplainers.weather} label="About this weather" />
          <dl className="grid grid-cols-2 gap-3">
            <Item
              label="Conditions"
              value={
                weather.condition === null
                  ? '—'
                  : (CONDITION_LABELS[weather.condition] ?? weather.condition)
              }
            />
            <Item
              label="Temperature"
              value={`${formatTemp(weather.temp_f)} (feels ${formatTemp(weather.apparent_f)})`}
            />
            <Item label="Wind" value={weather.wind_mph === null ? '—' : windText(weather)} />
            <Item label="Precipitation" value={formatPrecip(weather.precip_in)} />
            <Item label="Cloud cover" value={formatPercent(weather.cloud_pct, 0)} />
            <Item label="Humidity" value={formatPercent(weather.humidity_pct, 0)} />
            <Item label="Pressure" value={formatPressure(weather.pressure_hpa)} />
          </dl>
        </>
      )}
    </Card>
  );
}
