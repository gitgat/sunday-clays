import { Download } from 'lucide-react';
import { useRef, useState } from 'react';
import { WidenWindowButtons } from '../../components/WidenWindowButtons';
import { AboutBlock } from '../../components/ui/AboutBlock';
import { AdminPreviewBadge } from '../../components/ui/AdminPreviewBadge';
import { Card } from '../../components/ui/Card';
import { useFeature } from '../../lib/features';
import { downloadElementAsImage } from '../../lib/share';
import { useTimeWindow } from '../../lib/timeWindow';
import { ShareCard } from '../share/ShareCard';
import type { ProfileSection } from '../shooters/sections';
import { useShooterSummary } from './api';
import { SummaryCard } from './components/SummaryCard';
import { explainers } from './explainers';
import { summaryFilename, windowLine } from './format';

function SummarySection({ shooterId }: { shooterId: number }) {
  const { visible } = useFeature('summary_card');
  const { window, range, ready } = useTimeWindow();
  const query = useShooterSummary(shooterId, range, visible && ready);
  const cardRef = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);
  if (!visible) return null; // a bare section: no title, no gap
  const data = query.data;
  const filename =
    data === undefined || range === null
      ? ''
      : summaryFilename(data.display_name, range.from, range.to);
  return (
    <Card
      title={
        <span className="inline-flex flex-wrap items-center gap-2">
          Summary card
          <AdminPreviewBadge feature="summary_card" />
        </span>
      }
    >
      <div className="flex flex-col gap-3">
        <AboutBlock explainer={explainers['summary-card']} label="About the summary card" />
        {query.isError ? (
          <p role="alert">Could not load the summary.</p>
        ) : data === undefined || range === null ? (
          <p role="status">Loading the summary…</p>
        ) : data.sundays === 0 ? (
          <div className="flex flex-col gap-2">
            <p>No Sundays shot in this window.</p>
            <WidenWindowButtons />
          </div>
        ) : (
          <>
            <ShareCard filename={filename}>
              <div ref={cardRef}>
                <SummaryCard summary={data} windowText={windowLine(window, range)} />
              </div>
            </ShareCard>
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => {
                  setFailed(false);
                  const el = cardRef.current;
                  if (el !== null)
                    void downloadElementAsImage(el, filename).catch(() => setFailed(true));
                }}
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-button border border-outline-variant px-4"
              >
                <Download aria-hidden="true" className="size-4" />
                Download image
              </button>
              <span aria-live="polite" className="text-sm text-text-muted">
                {failed ? 'Could not create the image.' : ''}
              </span>
            </div>
          </>
        )}
      </div>
    </Card>
  );
}

/** Plan 19 §3.6.2: a shareable summary for the header window, just above Share (95). */
export const profileSection: ProfileSection = {
  id: 'summary',
  title: 'Summary card',
  order: 90,
  bare: true,
  Component: SummarySection,
};
