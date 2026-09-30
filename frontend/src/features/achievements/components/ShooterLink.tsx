import { Link } from 'react-router';
import { useRoundTypeLink } from '../../../lib/roundTypes';

/** A shooter name that links to the profile, keeping the global round-type filter (`rt`). */
export function ShooterLink({ shooterId, name }: { shooterId: number; name: string }) {
  const to = useRoundTypeLink(`/shooters/${shooterId}`);
  return (
    <Link to={to} className="inline-flex min-h-11 min-w-11 items-center underline">
      {name}
    </Link>
  );
}
