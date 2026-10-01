import { ChartLine } from 'lucide-react';
import { useId, useState } from 'react';
import { Link } from 'react-router';
import { useExplicitWindow } from '../../../lib/timeWindowChoice';
import { ExplainerToggle } from '../../../components/ui/Explainer';
import { InsightBump } from '../../bumps/BumpsProvider';
import type { Insight } from '../api';
import { chartHref } from '../chartLink';
import { Segments } from '../segments';
import { InsightExplainer } from './InsightExplainer';

export interface InsightCardProps {
  insight: Insight;
  /** "That's me" viewing their own insight: the second-person wording (spec §3.5). */
  you?: boolean;
  /** Extra classes for the list item (a grid span on desktop). */
  className?: string;
}

/**
 * One insight: its headline, a "New" tag, "See the chart" (the evidence, spec §3.6) and "How we
 * worked it out". A list item: feeds render these inside a list.
 */
export function InsightCard({ insight, you = false, className = '' }: InsightCardProps) {
  const [open, setOpen] = useState(false);
  const viewerWindow = useExplicitWindow();
  const panelId = useId();
  const headline = you && insight.headline_you !== null ? insight.headline_you : insight.headline;
  const chart = insight.chart;
  const label = you && chart.label_you ? chart.label_you : chart.label;
  return (
    <li
      data-insight-key={insight.key}
      className={`flex min-w-0 flex-col gap-2 border-t border-outline-variant pt-3 first:border-t-0 first:pt-0 ${className}`.trim()}
    >
      <p className="break-words text-base text-text">
        {insight.is_new && (
          <span className="mr-2 rounded-button bg-primary px-2 py-0.5 align-middle text-xs font-bold">
            New
          </span>
        )}
        <Segments segments={headline} />
      </p>
      <div className="flex flex-wrap items-center gap-x-2">
        <Link
          to={chartHref(chart, viewerWindow)}
          aria-label={`See the chart: ${label}`}
          className="inline-flex min-h-11 items-center gap-2 rounded-button px-3 text-sm text-accent hover:underline"
        >
          <ChartLine aria-hidden="true" className="size-4" />
          See the chart
        </Link>
        {chart.also.map((extra, i) => {
          const text = you && extra.label_you ? extra.label_you : extra.label;
          return (
            <Link
              key={`${String(i)}-${extra.anchor ?? ''}`}
              to={chartHref(extra, viewerWindow)}
              aria-label={`See the chart: ${text}`}
              className="inline-flex min-h-11 items-center rounded-button px-3 text-sm text-accent hover:underline"
            >
              {text}
            </Link>
          );
        })}
        <ExplainerToggle
          label="How we worked it out"
          panelId={panelId}
          open={open}
          onToggle={() => setOpen((v) => !v)}
        />
        <InsightBump insightKey={insight.key} />
      </div>
      {open && <InsightExplainer id={panelId} insight={insight} you={you} />}
    </li>
  );
}
