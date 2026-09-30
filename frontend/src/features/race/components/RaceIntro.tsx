import { raceIntro } from '../explainers';
import type { RaceMode } from '../labels';

/** Always-visible plain-words intro: what the race shows, how points work, and what the chosen mode means. */
export function RaceIntro({ mode }: { mode: RaceMode }) {
  const intro = raceIntro(mode);
  return (
    <section aria-label="About the race" className="min-w-0 rounded-card bg-elevated p-4 text-sm">
      <p>{intro.what}</p>
      <p className="mt-2">{intro.points}</p>
      <p className="mt-2 font-medium">{intro.mode}</p>
    </section>
  );
}
