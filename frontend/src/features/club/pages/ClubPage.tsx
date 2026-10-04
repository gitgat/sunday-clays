import { useId } from 'react';
import type { ReactNode } from 'react';
import { PageTopSlot } from '../../../components/layout/pageTop';
import { CardHeadingLevel } from '../../../components/ui/Card';
import { LazyChart } from '../components/LazyChart';
import { MilestonesSection } from '../components/MilestonesSection';
import { RegularsCard } from '../components/RegularsCard';
import { SummaryStats } from '../components/SummaryStats';

// The charts (and so ECharts) load in their own chunks: the header, the stats and the regulars
// never wait for them, and each chart holds its place with a titled loading card meanwhile.
const loadCharts = () => import('../components/ClubCharts');
type ChartName = keyof Awaited<ReturnType<typeof loadCharts>>;

/** A chart of ClubCharts in its own lazy slot; `wide` spans both columns on a wide screen. */
function Chart({ title, name, wide }: { title: string; name: ChartName; wide?: boolean }) {
  return (
    <div className={wide ? 'min-w-0 lg:col-span-2' : 'min-w-0'}>
      <LazyChart title={title} load={async () => ({ default: (await loadCharts())[name] })} />
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  const id = useId();
  return (
    <section aria-labelledby={id} className="flex flex-col gap-3">
      <h2 id={id} className="text-xl font-medium">
        {title}
      </h2>
      {/* grid-cols-1 is minmax(0, 1fr): an implicit auto track would grow to a card header's min-content and scroll the page sideways at 390 px. */}
      <CardHeadingLevel value={3}>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">{children}</div>
      </CardHeadingLevel>
    </section>
  );
}

const YEAR_BY_YEAR = "Year by year (every year; the time window doesn't apply)";

export function ClubPage() {
  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-3">
        <h1 className="text-2xl font-medium">Club</h1>
        <SummaryStats />
      </header>
      <PageTopSlot page="club" />
      <MilestonesSection />
      <Section title="Attendance">
        <Chart title="Attendance per Sunday" name="AttendanceChart" />
        <Chart title="Turnout vs weather" name="TurnoutWeatherCard" />
      </Section>
      <Section title="Scores">
        <Chart title="Median and top score" name="ScoreTrendChart" />
        <Chart title="Difficulty by Sunday" name="DifficultyChart" wide />
      </Section>
      <Section title="Membership">
        <Chart title="First rounds" name="FirstRoundsChart" />
        <div className="min-w-0 lg:col-span-2">
          <RegularsCard />
        </div>
      </Section>
      <Section title={YEAR_BY_YEAR}>
        <Chart title="Shooters and Sundays per year" name="YearTrendsChart" />
        <Chart title="Seasonality" name="SeasonalityChart" />
        <Chart title="Score distribution by year" name="DistributionChart" />
        <Chart title="Newcomers per year" name="NewcomersChart" />
        <Chart title="Newcomer retention" name="RetentionChart" />
        <Chart title="Rounds by member status" name="MemberGuestChart" />
        <Chart title="Guest → member conversion" name="ConversionChart" />
        <Chart title="How open is the competition?" name="ParityChart" wide />
      </Section>
    </div>
  );
}
