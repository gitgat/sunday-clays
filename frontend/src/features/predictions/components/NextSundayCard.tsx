import { useSyncExternalStore } from 'react';
import { Link } from 'react-router';
import { Card } from '../../../components/ui/Card';
import { isMeSkipped, subscribeMe } from '../../../lib/me';
import { useRoundTypeLink } from '../../../lib/roundTypes';
import { useNextPredictions, type NextPredictions } from '../api';
import { explainers } from '../explainers';
import {
  difficultyNote,
  expectationSentence,
  forecastSummary,
  formatDay,
  formatScore,
} from '../format';
import { AboutBlock } from '../../../components/ui/AboutBlock';

function YourExpectation({ data, meId }: { data: NextPredictions; meId: number | null }) {
  const shootersLink = useRoundTypeLink('/shooters');
  // Live, like Home's own question: a skip changes this copy in the same render.
  const skipped = useSyncExternalStore(subscribeMe, isMeSkipped);
  if (meId === null) {
    return (
      <div className="flex flex-col gap-2">
        {skipped ? (
          <p>Choose “That’s me” on your Shooters profile to see your own expected score here.</p>
        ) : (
          <p>
            To see your own expected score here, pick your name in “Which one are you?” or choose
            “That’s me” on your Shooters profile.
          </p>
        )}
        <Link to={shootersLink} className="inline-flex min-h-11 items-center self-start underline">
          Go to Shooters
        </Link>
      </div>
    );
  }
  const mine = data.shooters.find((s) => s.shooter_id === meId);
  if (mine === undefined) {
    return (
      <p>
        No expected score for you yet. It builds from the Sundays you shoot, out of the last 13.
      </p>
    );
  }
  return (
    <p>
      <span className="text-text-muted">Your expected score: </span>
      {expectationSentence(mine)}
    </p>
  );
}

function Body({ data, meId }: { data: NextPredictions; meId: number | null }) {
  return (
    <div className="flex min-w-0 flex-col gap-3">
      {data.forecast === null ? (
        <p>No forecast yet. It appears a few days before the shoot.</p>
      ) : (
        <p>Forecast 10:00–12:00: {forecastSummary(data.forecast)}</p>
      )}
      {data.model_ready ? (
        <>
          <dl className="grid grid-cols-1 gap-x-4 gap-y-1 sm:grid-cols-2">
            <div className="min-w-0">
              <dt className="text-text-muted">Predicted field median</dt>
              <dd className="text-lg">
                {data.field_median === null ? '—' : formatScore(data.field_median)}
              </dd>
            </div>
            <div className="min-w-0">
              <dt className="text-text-muted">Expected turnout</dt>
              <dd className="text-lg">About {Math.round(data.expected_turnout)} shooters</dd>
            </div>
          </dl>
          {data.shooters.length === 0 && <p>Nobody has shot in the last 13 Sundays.</p>}
          <p className="text-sm text-text-muted">{difficultyNote(data)}</p>
          <YourExpectation data={data} meId={meId} />
          <AboutBlock label="About these predictions" explainer={explainers['next-sunday']} />
        </>
      ) : (
        <p>Predictions appear after the first analytics run.</p>
      )}
    </div>
  );
}

/** Home "Next Sunday" card (C10 home widget, slot `main`). */
export function NextSundayCard({ meId }: { meId: number | null }) {
  const query = useNextPredictions();
  return (
    <Card title="Next Sunday" subtitle={query.data ? formatDay(query.data.target_date) : undefined}>
      {query.isPending ? (
        <p role="status">Loading predictions…</p>
      ) : query.isError ? (
        <p role="alert">Could not load predictions.</p>
      ) : (
        <Body data={query.data} meId={meId} />
      )}
    </Card>
  );
}
