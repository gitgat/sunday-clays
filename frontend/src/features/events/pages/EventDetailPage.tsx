import { lazy, Suspense, useMemo } from 'react';
import { Link, useParams } from 'react-router';
import { ApiError } from '../../../api/errors';
import { useChartTarget, useScrollToTarget } from '../../../components/charts/chartTarget';
import { Card } from '../../../components/ui/Card';
import { Skeleton } from '../../../components/ui/Skeleton';
import { Stat } from '../../../components/ui/Stat';
import { useRoundTypeHref } from '../../../lib/roundTypes';
import { isoDateCodec } from '../../../lib/useUrlState';
import { useAllSundays, useEvent } from '../api';
import type { EventDetail } from '../api';
import { About } from '../components/About';
import { EventSections } from '../components/EventSections';
import { NotablesCard } from '../components/NotablesCard';
import { Notice } from '../components/Notice';
import { highlightedShooters, ResultsTable } from '../components/ResultsTable';
import { VsPrevCard } from '../components/VsPrevCard';
import { SpecialResultsTable } from '../components/SpecialResultsTable';
import { WeatherCard } from '../components/WeatherCard';
import { eventExplainers } from '../explainers';
import {
  difficultyHint,
  formatDay,
  formatScore,
  formatSigned,
  isSpecial,
  neighbourSundays,
  roundTypeLabel,
  specialLine,
  targetsOf,
} from '../format';
import { eventSections, sectionsAt } from '../sections';
import type { EventSection } from '../sections';

// ECharts is the heaviest chunk and only events with a station sheet chart anything: load on demand.
const StationHeatmap = lazy(async () => ({
  default: (await import('../components/StationHeatmap')).StationHeatmap,
}));

const SOURCE_NOTES: Record<string, string> = {
  stations: ' (from station sheets)',
  override: ' (admin override)',
};

/** Review Focus #3: a Sunday without scores says why, never NaN, null or an empty results table. */
export function attendanceOnlyTitle(headCount: number | null): string {
  return headCount === null
    ? 'No scores recorded for this Sunday'
    : `Attendance only — ${headCount} shooters, no scores recorded`;
}

/** Decision 20: the counting rule, in neutral words. */
const SPECIAL_NOTE =
  'A special shoot counts as a Sunday shot for everyone who came, so it keeps streaks going. Its scores stay out of averages, best scores, records and leaderboards.';

function SpecialEvent({ event }: { event: EventDetail }) {
  useScrollToTarget('results', true);
  const stations = event.stations?.layout.length ?? null;
  return (
    <>
      <p role="note" className="rounded-card border border-accent p-3">
        {SPECIAL_NOTE}
      </p>
      <Card title="This Sunday">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          <Stat
            label="Shooters"
            value={String(event.n_shooters)}
            explainer={eventExplainers.shooters}
          />
          <Stat
            label="Targets"
            value={String(targetsOf(event))}
            explainer={eventExplainers.special}
          />
          <Stat
            label="Stations"
            value={stations === null ? '—' : String(stations)}
            explainer={eventExplainers.stations}
          />
        </div>
      </Card>
      <Card id="chart-results" title="Results">
        <SpecialResultsTable results={event.results} targetTotal={targetsOf(event)} />
      </Card>
      {event.stations !== null && (
        <Suspense
          fallback={
            <Card title="Station hits">
              <Skeleton label="Loading station hits" />
            </Card>
          }
        >
          <StationHeatmap
            stations={event.stations}
            results={event.results}
            date={event.event_date}
          />
        </Suspense>
      )}
    </>
  );
}

function ScoredEvent({ event }: { event: EventDetail }) {
  const { target } = useChartTarget('results');
  const highlighted = useMemo(() => highlightedShooters(target.hl), [target.hl]);
  useScrollToTarget('results', true);
  return (
    <>
      {!event.results_complete && event.head_count !== null && (
        <p role="note" className="rounded-card border border-accent p-3">
          {`Partial results — ${event.n_shooters} of ${event.head_count} shooters recorded.`}
        </p>
      )}
      <Card title="This Sunday">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
          <Stat
            label="Shooters"
            value={String(event.n_shooters)}
            explainer={eventExplainers.shooters}
          />
          <Stat
            label="Head count"
            value={event.head_count === null ? '—' : String(event.head_count)}
            explainer={eventExplainers.headCount}
          />
          <Stat
            label="Median"
            value={formatScore(event.median)}
            explainer={eventExplainers.median}
          />
          <Stat
            label="Top score"
            value={formatScore(event.top_score)}
            explainer={eventExplainers.topScore}
          />
          <Stat
            label="Difficulty"
            value={formatSigned(event.difficulty)}
            hint={difficultyHint(event.difficulty)}
            explainer={eventExplainers.difficulty}
          />
        </div>
      </Card>
      <Card id="chart-results" title="Results">
        <About explainer={eventExplainers.results} label="About these results" />
        <ResultsTable
          results={event.results}
          complete={event.results_complete}
          highlight={highlighted}
        />
      </Card>
      {event.stations !== null && (
        <Suspense
          fallback={
            <Card title="Station hits">
              <Skeleton label="Loading station hits" />
            </Card>
          }
        >
          <StationHeatmap
            stations={event.stations}
            results={event.results}
            date={event.event_date}
          />
        </Suspense>
      )}
    </>
  );
}

const NAV_LINK =
  'inline-flex min-h-11 min-w-11 items-center gap-1 text-text underline underline-offset-2';

/** ‹ Previous / Next › Sunday: the neighbouring Sundays with scores, keeping the global filters. */
function SundayNav({ date }: { date: string }) {
  const href = useRoundTypeHref();
  const sundays = useAllSundays();
  if (!sundays.data) return null;
  const { prev, next } = neighbourSundays(sundays.data, date);
  if (prev === null && next === null) return null;
  return (
    <nav aria-label="Other Sundays" className="flex items-center justify-between gap-2">
      {prev === null ? (
        <span />
      ) : (
        <Link to={href(`/events/${prev}`)} className={NAV_LINK}>
          <span aria-hidden="true">‹</span> Previous Sunday
          <span className="sr-only"> ({formatDay(prev)})</span>
        </Link>
      )}
      {next === null ? (
        <span />
      ) : (
        <Link to={href(`/events/${next}`)} className={NAV_LINK}>
          Next Sunday <span className="sr-only">({formatDay(next)}) </span>
          <span aria-hidden="true">›</span>
        </Link>
      )}
    </nav>
  );
}

function EventDetailView({ event, sections }: { event: EventDetail; sections: EventSection[] }) {
  const special = isSpecial(event);
  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-medium">{formatDay(event.event_date)}</h1>
        <p className="text-text-muted">
          {special ? (
            <span>{specialLine(event)}</span>
          ) : (
            <>
              <span>{roundTypeLabel(event.round_type)}</span>
              {SOURCE_NOTES[event.round_type_source] ?? ''}
            </>
          )}
        </p>
      </header>
      <SundayNav date={event.event_date} />
      <EventSections date={event.event_date} sections={sectionsAt(sections, 'top')} />
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="flex min-w-0 flex-col gap-4 lg:col-span-2">
          {special ? (
            <SpecialEvent event={event} />
          ) : event.has_scores ? (
            <ScoredEvent event={event} />
          ) : (
            <Notice level={2} title={attendanceOnlyTitle(event.head_count)} />
          )}
        </div>
        <div className="flex min-w-0 flex-col gap-4">
          <WeatherCard weather={event.weather} />
          {event.has_scores && !special && <VsPrevCard vsPrev={event.vs_prev} />}
          {event.has_scores && <NotablesCard notables={event.notables} />}
        </div>
      </div>
      <EventSections date={event.event_date} sections={sectionsAt(sections, 'bottom')} />
    </div>
  );
}

/** No Sunday at this URL: the message is the page's h1, with a way back to the calendar. */
function EventNotFound({ title }: { title: string }) {
  const href = useRoundTypeHref();
  return (
    <Notice level={1} title={title}>
      Pick a date from the{' '}
      <Link
        to={href('/events')}
        className="inline-flex min-h-11 min-w-11 items-center text-text underline underline-offset-2"
      >
        calendar
      </Link>
      .
    </Notice>
  );
}

export function EventDetailPage({ sections = eventSections }: { sections?: EventSection[] }) {
  const { date = '' } = useParams();
  const event = useEvent(date);
  // A crafted URL (/events/0, /events/2026-02-30) is not a date: never formatted, never requested.
  if (isoDateCodec.parse(date) === null) return <EventNotFound title="Sunday not found" />;
  if (event.isPending) {
    return (
      <div className="flex flex-col gap-4">
        <h1 className="text-2xl font-medium">{formatDay(date)}</h1>
        <Skeleton className="h-96" />
      </div>
    );
  }
  if (event.isError) {
    const status = event.error instanceof ApiError ? event.error.status : null;
    if (status === 404) return <EventNotFound title={`Nothing on file for ${formatDay(date)}`} />;
    // 422: the server rejects a date the client accepted (e.g. year 0).
    if (status === 422) return <EventNotFound title="Sunday not found" />;
    return (
      <Notice level={1} title="Couldn't load this Sunday">
        {event.error.message}
      </Notice>
    );
  }
  return <EventDetailView event={event.data} sections={sections} />;
}
