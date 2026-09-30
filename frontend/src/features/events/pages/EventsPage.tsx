import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '../../../components/ui/Button';
import { Skeleton } from '../../../components/ui/Skeleton';
import { isCustomWindow, parseCustomWindow, useWindowChoice } from '../../../lib/timeWindowChoice';
import { ROUND_TYPE_LABELS, useRoundTypes } from '../../../lib/roundTypes';
import { intCodec, useUrlState } from '../../../lib/useUrlState';
import { useEvents, useEventsAnyRoundType, useMeta } from '../api';
import type { Meta } from '../api';
import { EventList } from '../components/EventList';
import { Notice } from '../components/Notice';
import { SeasonCalendar } from '../components/SeasonCalendar';

interface Seasons {
  first: number;
  last: number;
}

function yearOf(iso: string | null | undefined): number | null {
  return iso ? Number(iso.slice(0, 4)) : null;
}

/** The first and last season with an event; the current year alone when meta is empty or failed. */
function seasonsOf(meta: Meta | undefined): Seasons {
  const last = yearOf(meta?.last_event_date) ?? new Date().getFullYear();
  return { first: yearOf(meta?.first_event_date) ?? last, last };
}

/** `?year=` (0 = the latest season) clamped into the seasons, so a crafted year never escapes them. */
function pickSeason(requested: number, { first, last }: Seasons): number {
  return Math.min(Math.max(requested || last, first), last);
}

function Season({ seasons }: { seasons: Seasons }) {
  // intCodec: a missing or unreadable ?year= reads as 0, i.e. "the latest season".
  const [yearParam, setYear] = useUrlState('year', intCodec, 0);
  // A custom time window opens on the year it ends in (a Sunday-level pick, not a filter).
  // useWindowChoice, not useTimeWindow: a custom window carries its own dates, and useTimeWindow's
  // /api/meta query is the one that gates this page (an error there must not remount it).
  const [window] = useWindowChoice();
  const [roundTypes] = useRoundTypes();
  const customEnd = isCustomWindow(window) ? parseCustomWindow(window)?.to : undefined;
  const year = pickSeason(yearParam || yearOf(customEnd) || 0, seasons);
  const events = useEvents(year);
  const anyRoundType = useEventsAnyRoundType(year);
  const shown = new Set(events.data?.map((e) => e.event_date));
  const otherRoundType = (anyRoundType.data ?? [])
    .map((e) => e.event_date)
    .filter((d) => !shown.has(d));

  function body() {
    if (events.isPending) return <Skeleton className="h-96" />;
    if (events.isError) {
      return (
        <Notice level={2} title="Couldn't load Sundays">
          {events.error.message}
        </Notice>
      );
    }
    if (events.data.length === 0 && anyRoundType.isPending) return <Skeleton className="h-96" />;
    if (events.data.length === 0 && otherRoundType.length === 0) {
      return <Notice level={2} title={`No Sundays in ${year}`} />;
    }
    return (
      <div className="flex flex-col gap-4">
        {events.data.length === 0 && (
          <Notice
            level={2}
            title={`No ${roundTypes.map((t) => ROUND_TYPE_LABELS[t]).join(' or ')} Sundays in ${year}; ${otherRoundType.length} ${otherRoundType.length === 1 ? 'Sunday was' : 'Sundays were'} another round type.`}
          />
        )}
        <div className="grid gap-4 lg:grid-cols-2 lg:items-start">
          <SeasonCalendar year={year} events={events.data} otherRoundType={otherRoundType} />
          {events.data.length > 0 && <EventList year={year} events={events.data} />}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <header className="flex items-center justify-between gap-2">
        <Button
          variant="ghost"
          aria-label="Previous year"
          disabled={year <= seasons.first}
          onClick={() => setYear(year - 1)}
        >
          <ChevronLeft aria-hidden="true" />
        </Button>
        <h1 className="text-2xl font-medium">Sundays {year}</h1>
        <Button
          variant="ghost"
          aria-label="Next year"
          disabled={year >= seasons.last}
          onClick={() => setYear(year + 1)}
        >
          <ChevronRight aria-hidden="true" />
        </Button>
      </header>
      {body()}
    </div>
  );
}

export function EventsPage() {
  const meta = useMeta();
  // The season range comes from /api/meta, so ?year= is only read (and fetched) once it is known.
  if (meta.isPending) return <Skeleton className="h-96" />;
  return <Season seasons={seasonsOf(meta.data)} />;
}
