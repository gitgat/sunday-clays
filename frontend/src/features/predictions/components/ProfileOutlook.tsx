import { useNextPredictions, type NextPredictions } from '../api';
import { explainers } from '../explainers';
import { expectationSentence, formatDay } from '../format';
import { AboutBlock } from '../../../components/ui/AboutBlock';
import { useShooter } from '../../shooters/api';

function Outlook({ data, shooterId }: { data: NextPredictions; shooterId: number }) {
  if (!data.model_ready) return <p>Predictions appear after the first analytics run.</p>;
  const row = data.shooters.find((s) => s.shooter_id === shooterId);
  return (
    <>
      <p>
        {row === undefined
          ? `No expected score for ${formatDay(data.target_date)} yet. It builds from the Sundays shot, out of the last 13.`
          : expectationSentence(row)}
      </p>
      <AboutBlock label="About this expected score" explainer={explainers['next-sunday']} />
    </>
  );
}

/** Profile section: this shooter's own expectation for next Sunday (C10 profile section). */
export function ProfileOutlook({ shooterId }: { shooterId: number }) {
  const query = useNextPredictions();
  // Lifetime lookup (no window): only the deceased flag is read here.
  const shooter = useShooter(shooterId, null);
  // Nobody who has died is expected next Sunday; a failed shooter lookup just shows the outlook.
  if (shooter.data?.deceased === true) return null;
  return (
    <section aria-label="Next Sunday outlook" className="flex min-w-0 flex-col gap-2">
      {query.isPending || shooter.isPending ? (
        <p role="status">Loading predictions…</p>
      ) : query.isError ? (
        <p role="alert">Could not load predictions.</p>
      ) : (
        <Outlook data={query.data} shooterId={shooterId} />
      )}
    </section>
  );
}
