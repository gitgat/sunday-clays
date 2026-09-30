import { useId } from 'react';
import { inWindow, useWindowChoice, windowPhrase } from '../../../lib/timeWindowChoice';
import { enumCodec, intCodec, rangeCodec, useUrlState } from '../../../lib/useUrlState';
import type { Explainer } from '../../../components/charts/types';
import type { WeatherEvent } from '../api';
import { AboutThis } from './AboutThis';
import {
  GUST_MAX,
  TEMP_MAX,
  TEMP_MIN,
  filterEvents,
  summarize,
  type RainFilter,
} from '../conditions';
import { formatSigned } from '../format';

const TEMP_DEFAULT: [number, number] = [TEMP_MIN, TEMP_MAX];
const GUST_DEFAULT = GUST_MAX;
const RAIN_OPTIONS: readonly RainFilter[] = ['any', 'dry', 'wet'];
const rainCodec = enumCodec(RAIN_OPTIONS);

function formatMean(value: number | null, signed = false): string {
  if (value === null) return '—';
  return signed ? formatSigned(value) : value.toFixed(1);
}

/** Sliders over the weather of past Sundays; state lives in the URL (C10). */
export function ConditionsExplorer({
  events,
  explainer,
}: {
  events: WeatherEvent[];
  explainer?: Explainer | undefined;
}) {
  const titleId = useId();
  const [temp, setTemp] = useUrlState('temp', rangeCodec, TEMP_DEFAULT);
  const [gustMax, setGustMax] = useUrlState('gust', intCodec, GUST_DEFAULT);
  const [rain, setRain] = useUrlState('rain', rainCodec, 'any');
  const [lo, hi] = temp;
  const [window] = useWindowChoice();
  // "All" means every Sunday in the header window, so the column and the count name the period.
  const allLabel =
    window === 'all' ? 'All time' : `All, ${windowPhrase(window).replace(/^the /, '')}`;
  const picked = summarize(filterEvents(events, { temp, gustMax, rain }));
  const all = summarize(events);
  return (
    <section aria-labelledby={titleId} className="flex flex-col gap-3 rounded-card bg-elevated p-4">
      <h2 id={titleId} className="text-lg font-medium">
        Conditions explorer
      </h2>
      {explainer !== undefined && <AboutThis label="About this explorer" explainer={explainer} />}
      <div className="grid gap-3 md:grid-cols-2">
        <label className="flex flex-col gap-1">
          <span>
            Coldest: {lo}°F{lo <= TEMP_MIN ? ' or colder' : ''}
          </span>
          <input
            type="range"
            min={TEMP_MIN}
            max={TEMP_MAX}
            step={5}
            value={lo}
            onChange={(e) => setTemp([Math.min(Number(e.target.value), hi), hi])}
            className="min-h-11"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span>
            Warmest: {hi}°F{hi >= TEMP_MAX ? ' or warmer' : ''}
          </span>
          <input
            type="range"
            min={TEMP_MIN}
            max={TEMP_MAX}
            step={5}
            value={hi}
            onChange={(e) => setTemp([lo, Math.max(Number(e.target.value), lo)])}
            className="min-h-11"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span>
            Strongest gust: {gustMax}
            {gustMax >= GUST_MAX ? '+' : ''} mph
          </span>
          <input
            type="range"
            min={0}
            max={GUST_MAX}
            step={5}
            value={gustMax}
            onChange={(e) => setGustMax(Number(e.target.value))}
            className="min-h-11"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span>Rain</span>
          <select
            value={rain}
            onChange={(e) => setRain(e.target.value as RainFilter)}
            className="min-h-11 rounded-button bg-surface px-3"
          >
            <option value="any">Any</option>
            <option value="dry">Dry</option>
            <option value="wet">Wet</option>
          </select>
        </label>
      </div>
      <p>
        {picked.events} of {all.events} Sundays {inWindow(window)} match.
      </p>
      <dl className="grid grid-cols-3 gap-2">
        <dt />
        <dd className="text-text-muted">Matching</dd>
        <dd className="text-text-muted">{allLabel}</dd>
        <dt className="text-text-muted">Mean field median</dt>
        <dd>{formatMean(picked.meanMedian)}</dd>
        <dd>{formatMean(all.meanMedian)}</dd>
        <dt className="text-text-muted">Mean difficulty</dt>
        <dd>{formatMean(picked.meanDifficulty, true)}</dd>
        <dd>{formatMean(all.meanDifficulty, true)}</dd>
      </dl>
    </section>
  );
}
