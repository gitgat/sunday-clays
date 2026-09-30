import { AboutBlock } from '../../components/ui/AboutBlock';
import { useShooterAchievements } from './api';
import { explainers } from './explainers';
import { ProgressBar } from './components/ProgressBar';
import { TrophyIcon } from './components/TrophyIcon';
import { formatCount } from './labels';

/** Home widget (slot `me`); the host passes the per-device "That's me" id (Plan 08 D5). */
export function NextTrophy({ meId }: { meId: number | null }) {
  const { data, isPending, isError } = useShooterAchievements(meId);
  if (meId === null) {
    return (
      <p className="text-text-muted">
        Tap “That’s me” on your shooter profile to see your next trophy.
      </p>
    );
  }
  if (isPending) return <p role="status">Loading your next trophy…</p>;
  if (isError) return <p role="alert">Could not load your trophies.</p>;
  const next = data.progress
    .flatMap((p) => (p.next_threshold === null ? [] : [{ ...p, next_threshold: p.next_threshold }]))
    .sort((a, b) => b.fraction - a.fraction || a.code.localeCompare(b.code))
    .slice(0, 3);
  return (
    <section aria-label="Your next trophy" className="flex flex-col gap-3">
      <h3 className="text-lg font-medium">Your next trophy</h3>
      <AboutBlock explainer={explainers['next-trophy']} label="About your next trophy" />
      {next.length === 0 ? (
        <p>Every tier earned — legendary.</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {next.map((p) => (
            <li key={p.code} className="flex items-center gap-3">
              <TrophyIcon artKey={p.art_key} metal={p.next_metal} locked size={40} />
              <span className="flex flex-1 flex-col gap-1">
                <span className="font-medium">{p.name}</span>
                <ProgressBar value={p.value} max={p.next_threshold} label={`${p.name} progress`} />
                <span className="text-sm text-text-muted">
                  {formatCount(p.value)} / {p.next_label}
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
