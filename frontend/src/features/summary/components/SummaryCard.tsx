import type { ShooterSummary } from '../api';
import { summaryLines } from '../format';

/** The element rendered to an image (max 480 px). Only positive or neutral facts (R2). */
export function SummaryCard({
  summary,
  windowText,
}: {
  summary: ShooterSummary;
  windowText: string;
}) {
  return (
    <article className="flex max-w-[480px] flex-col gap-2 rounded-card bg-surface p-4 text-text">
      <p className="text-sm text-accent">Sunday Clays · Tri-County Gun Club</p>
      <h3 className="break-words text-xl font-bold">{summary.display_name}</h3>
      <p className="text-sm text-text-muted">{windowText}</p>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
        {summaryLines(summary).map(([label, value, extra]) => (
          <div key={label} className="contents">
            <dt className="text-text-muted">{label}</dt>
            <dd>
              {value}
              {extra !== '' && <span className="ml-2 text-sm text-text-muted">{extra}</span>}
            </dd>
          </div>
        ))}
      </dl>
      <p className="text-xs text-text-muted">All round types · sundayclays.claysmasher.com</p>
    </article>
  );
}
