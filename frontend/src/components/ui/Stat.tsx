import { ArrowDown, ArrowUp, Minus } from 'lucide-react';
import { useId, useState, type ReactNode } from 'react';
import type { Explainer } from '../charts/types';
import { cx } from './cx';
import { ExplainerPanel, ExplainerToggle, ScopeTag } from './Explainer';

export interface StatProps {
  label: string;
  value: ReactNode;
  /** Change vs a previous value; rendered with an arrow, a word for screen readers and its sign. */
  delta?: number | null;
  formatDelta?: (magnitude: number) => string;
  hint?: string;
  /** Plain-language copy behind a compact ? button under the label. */
  explainer?: Explainer;
}

/** Only the aria-hidden arrow takes the trend color (a graphic, 3:1); the number stays text-text. */
const TREND = {
  up: { Arrow: ArrowUp, word: 'up', sign: '+', stroke: 'stroke-accent' },
  down: { Arrow: ArrowDown, word: 'down', sign: '−', stroke: 'stroke-error' },
  flat: { Arrow: Minus, word: 'no change', sign: '', stroke: 'stroke-text-muted' },
} as const;

function trendOf(delta: number | null | undefined) {
  if (typeof delta !== 'number' || !Number.isFinite(delta)) return null;
  const key = delta > 0 ? 'up' : delta < 0 ? 'down' : 'flat';
  return { key, magnitude: Math.abs(delta), ...TREND[key] };
}

export function Stat({
  label,
  value,
  delta,
  formatDelta = (n) => n.toFixed(1),
  hint,
  explainer,
}: StatProps) {
  const trend = trendOf(delta);
  const [open, setOpen] = useState(false);
  const panelId = useId();
  return (
    <div className="flex min-w-0 flex-col">
      {explainer === undefined ? (
        <span className="text-xs uppercase tracking-wide text-text-muted">{label}</span>
      ) : (
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs uppercase tracking-wide text-text-muted">{label}</span>
          <ExplainerToggle
            compact
            label={`About ${label}`}
            panelId={panelId}
            open={open}
            onToggle={() => setOpen((v) => !v)}
          />
        </div>
      )}
      <span className="text-2xl font-medium text-text">{value}</span>
      {trend !== null && (
        <span data-trend={trend.key} className="inline-flex items-center gap-1 text-sm">
          <trend.Arrow aria-hidden="true" className={cx('size-3.5 shrink-0', trend.stroke)} />
          <span className="sr-only">{trend.word} </span>
          <span className="text-text">
            {trend.sign}
            {formatDelta(trend.magnitude)}
          </span>
        </span>
      )}
      {hint !== undefined && <span className="text-xs text-text-muted">{hint}</span>}
      {explainer !== undefined && (
        <>
          <div className="flex">
            <ScopeTag scope={explainer.scope} />
          </div>
          {open && (
            <div className="mt-2">
              <ExplainerPanel id={panelId} explainer={explainer} />
            </div>
          )}
        </>
      )}
    </div>
  );
}
