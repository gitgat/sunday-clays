import { useEventAchievements } from './api';
import { ShooterLink } from './components/ShooterLink';
import { TrophyIcon } from './components/TrophyIcon';
import { trophyTitle } from './labels';

export function TrophiesToday({ date }: { date: string }) {
  const { data, isPending, isError } = useEventAchievements(date);
  if (isPending) return <p role="status">Loading trophies…</p>;
  if (isError) return <p role="alert">Could not load trophies for this Sunday.</p>;
  if (data.awards.length === 0)
    return <p className="text-text-muted">No trophies were earned this Sunday.</p>;
  return (
    <ul aria-label="Trophies earned today" className="flex flex-col gap-2">
      {data.awards.map((award) => (
        <li
          key={`${award.shooter_id}-${award.code}`}
          className="flex min-h-11 flex-wrap items-center gap-x-3"
        >
          <TrophyIcon artKey={award.art_key} metal={award.metal} locked={false} size={32} />
          <span>
            <ShooterLink shooterId={award.shooter_id} name={award.display_name} /> —{' '}
            {trophyTitle(award)}
          </span>
        </li>
      ))}
    </ul>
  );
}
