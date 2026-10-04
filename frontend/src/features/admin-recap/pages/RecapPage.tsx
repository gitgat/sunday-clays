import { useMemo, useRef, useState } from 'react';
import { AdminPreviewBadge } from '../../../components/ui/AdminPreviewBadge';
import { Select } from '../../../components/ui/Select';
import { Tabs } from '../../../components/ui/Tabs';
import { downloadElementAsImage } from '../../../lib/share';
import { optionalIsoDateCodec, useUrlState } from '../../../lib/useUrlState';
import { formatDay } from '../../home/format';
import { useRecap, useRecapSundays } from '../api';
import { RecapImageCard } from '../components/RecapImageCard';
import { formatRecap, recapFilename } from '../format';

type Tab = 'text' | 'markdown';
const TABS = [
  { value: 'text', label: 'Plain text' },
  { value: 'markdown', label: 'Markdown' },
] as const;
const BUTTON =
  'inline-flex min-h-11 items-center justify-center rounded-button border border-outline-variant px-4 text-sm';

async function copy(text: string, area: HTMLTextAreaElement | null): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    area?.select();
    return document.execCommand('copy');
  }
}

/** Admin tool (Plan 19 §3.3.2): one Sunday as paste-ready text, Markdown and an image. */
export function RecapPage() {
  const sundays = useRecapSundays();
  const held = useMemo(
    () =>
      (sundays.data ?? [])
        .filter((e) => e.results_complete)
        .sort((a, b) => b.event_date.localeCompare(a.event_date)),
    [sundays.data],
  );
  const [chosen, setChosen] = useUrlState<string | null>('date', optionalIsoDateCodec, null);
  // A held Sunday from the data (never "today", D26); a ?date= that is not one falls back.
  const date = held.some((e) => e.event_date === chosen) ? chosen : (held[0]?.event_date ?? null);
  const recap = useRecap(date);
  const [tab, setTab] = useState<Tab>('text');
  const [message, setMessage] = useState('');
  const areaRef = useRef<HTMLTextAreaElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  const formatted = recap.data === undefined ? null : formatRecap(recap.data);
  const shown = formatted === null ? '' : tab === 'text' ? formatted.text : formatted.markdown;

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-center gap-2">
        <h1 className="text-2xl font-medium">Weekly recap</h1>
        <AdminPreviewBadge feature="weekly_recap" />
      </header>
      {held.length > 0 && date !== null && (
        <Select
          label="Sunday"
          value={date}
          onChange={(value) => {
            setMessage('');
            setChosen(value);
          }}
          options={held.map((e) => ({
            value: e.event_date,
            label:
              e.kind === 'special' && e.label
                ? `${formatDay(e.event_date)} — ${e.label}`
                : formatDay(e.event_date),
          }))}
        />
      )}
      {sundays.isError ? (
        <p role="alert">Could not load the Sundays.</p>
      ) : sundays.isPending ? (
        <p role="status">Loading the recap…</p>
      ) : date === null ? (
        <p>No Sunday has full results yet.</p>
      ) : recap.isError ? (
        <p role="alert">Could not build the recap for this Sunday.</p>
      ) : formatted === null || recap.data === undefined ? (
        <p role="status">Loading the recap…</p>
      ) : (
        <>
          <Tabs
            label="Format"
            tabs={TABS}
            value={tab}
            onChange={(next) => {
              setMessage('');
              setTab(next);
            }}
          />
          <textarea
            ref={areaRef}
            readOnly
            aria-label={tab === 'text' ? 'Recap (plain text)' : 'Recap (Markdown)'}
            value={shown}
            rows={shown.split('\n').length + 1}
            className="w-full rounded-card border border-outline-variant bg-surface p-3 font-mono text-sm text-text"
          />
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              className={BUTTON}
              onClick={() =>
                void copy(shown, areaRef.current).then((ok) =>
                  setMessage(
                    ok ? 'Copied.' : 'Could not copy. Select the text and copy it by hand.',
                  ),
                )
              }
            >
              {tab === 'text' ? 'Copy text' : 'Copy Markdown'}
            </button>
            <button
              type="button"
              className={BUTTON}
              onClick={() => {
                const el = cardRef.current;
                if (el === null || date === null) return;
                void downloadElementAsImage(el, recapFilename(date)).then(
                  () => setMessage('Image ready.'),
                  () => setMessage('Could not create the image.'),
                );
              }}
            >
              Download image
            </button>
            <span aria-live="polite" className="text-sm text-text-muted">
              {message}
            </span>
          </div>
          <div className="overflow-x-auto">
            <RecapImageCard recap={recap.data} />
          </div>
          {/* The PNG is drawn from this fixed 600 px copy, so a phone gets the same image as a
              desktop. It sits off screen (fixed, so it adds no scroll) and is hidden from readers. */}
          <div aria-hidden="true" className="pointer-events-none fixed top-0 -left-[10000px]">
            <div ref={cardRef} className="w-[600px]">
              <RecapImageCard recap={recap.data} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
