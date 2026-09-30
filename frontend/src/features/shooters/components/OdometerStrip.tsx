import { useId } from 'react';
import type { Odometer } from '../api';
import { explainers } from '../explainers';
import { monthName } from '../format';
import { AllRoundTypesTag, InlineExplainer } from './InlineExplainer';

export function odometerItems(o: Odometer): { label: string; value: string }[] {
  const count = (n: number) => n.toLocaleString('en-US');
  return [
    { label: 'Clays thrown', value: count(o.clays_thrown) },
    { label: 'Clays broken', value: count(o.clays_broken) },
    {
      label: 'Hit rate',
      value: o.clays_thrown > 0 ? `${((100 * o.clays_broken) / o.clays_thrown).toFixed(1)}%` : '—',
    },
    { label: 'Rounds', value: count(o.rounds) },
    { label: 'Sundays', value: count(o.events) },
    { label: 'Years active', value: count(o.years_active) },
    { label: 'Current streak', value: count(o.current_streak) },
    { label: 'Longest streak', value: count(o.longest_streak) },
    {
      label: 'Favorite month',
      value: o.favorite_month === null ? '—' : monthName(o.favorite_month),
    },
    { label: 'Trophies', value: count(o.trophies) },
  ];
}

/** Lifetime totals: a visible heading tells them apart from the hero's round-type-filtered Rounds/Events. */
export function OdometerStrip({ odometer }: { odometer: Odometer }) {
  const headingId = useId();
  return (
    <div className="flex flex-col gap-2 rounded-card bg-elevated p-3">
      <div className="flex flex-wrap items-center gap-2">
        <h2 id={headingId} className="text-sm font-medium">
          Lifetime odometer
        </h2>
        <AllRoundTypesTag />
      </div>
      <InlineExplainer label="About the odometer" explainer={explainers.odometer} />
      <ul aria-labelledby={headingId} className="grid grid-cols-2 gap-2 sm:grid-cols-5">
        {odometerItems(odometer).map((item) => (
          <li key={item.label} className="flex flex-col">
            <span className="text-xs text-text-muted">{item.label}</span>
            <span className="text-lg tabular-nums">{item.value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
