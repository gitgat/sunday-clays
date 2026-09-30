import { Info } from 'lucide-react';
import { createElement, useContext } from 'react';
import type { Explainer } from '../charts/types';
import { useTimeWindow } from '../../lib/timeWindow';
import { windowTagText } from '../../lib/windowText';
import { CardHeadingLevel } from './Card';
import { cx } from './cx';

export interface ExplainerToggleProps {
  /** The accessible name, e.g. "About this chart". */
  label: string;
  /** id of the panel this button opens (aria-controls). */
  panelId: string;
  open: boolean;
  onToggle: () => void;
  /** A "?" with the same accessible name, for stats. */
  compact?: boolean;
}

/** The disclosure button: a 44 px target that says what it opens. */
export function ExplainerToggle({
  label,
  panelId,
  open,
  onToggle,
  compact = false,
}: ExplainerToggleProps) {
  return (
    <button
      type="button"
      aria-expanded={open}
      aria-controls={panelId}
      aria-label={compact ? label : undefined}
      onClick={onToggle}
      className={cx(
        'inline-flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-button text-sm text-text-muted hover:text-text',
        compact ? 'font-bold' : 'px-3',
      )}
    >
      {compact ? (
        '?'
      ) : (
        <>
          <Info aria-hidden="true" className="size-4" />
          {label}
        </>
      )}
    </button>
  );
}

function Part({
  title,
  level,
  children,
}: {
  title: string;
  level: number;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      {createElement(`h${level}`, { className: 'text-sm font-medium text-text' }, title)}
      {children}
    </div>
  );
}

function Bullets({ items }: { items: readonly string[] }) {
  return (
    <ul className="list-disc space-y-1 pl-5 text-sm text-text-muted">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

/** What a chart or stat shows, how to read it and how it is worked out, in three short parts. */
export function ExplainerPanel({ id, explainer }: { id: string; explainer: Explainer }) {
  // Headings nest under the card's own title (h2, or h3 inside a page section).
  const level = useContext(CardHeadingLevel) + 1;
  return (
    <div
      id={id}
      data-testid="explainer-panel"
      className="mb-3 flex min-w-0 flex-col gap-3 rounded-card border border-outline-variant bg-surface p-3"
    >
      <Part title="What this shows" level={level}>
        <p className="text-sm text-text-muted">{explainer.what}</p>
      </Part>
      {explainer.read !== undefined && explainer.read.length > 0 && (
        <Part title="How to read it" level={level}>
          <Bullets items={explainer.read} />
        </Part>
      )}
      <Part title="How it's worked out" level={level}>
        <Bullets items={explainer.computed} />
      </Part>
    </div>
  );
}

const SCOPE_TEXT = { 'all-time': 'All time', lifetime: 'Lifetime', year: 'One year at a time' };

/**
 * Which data a chart covers: the active time window's name with its dates ("Last 8 weeks · Aug 3 –
 * Sep 27"), "All time", "Lifetime" or "One year at a time". Nothing without a scope.
 */
export function ScopeTag({ scope }: { scope: Explainer['scope'] }) {
  if (scope === undefined) return null;
  return scope === 'windowed' ? <WindowedTag /> : <Tag text={SCOPE_TEXT[scope]} />;
}

function WindowedTag() {
  const { window, range } = useTimeWindow();
  return <Tag text={windowTagText(window, range)} />;
}

function Tag({ text }: { text: string }) {
  return (
    <span className="rounded-button border border-outline-variant px-2 py-0.5 text-xs text-text-muted">
      {text}
    </span>
  );
}
