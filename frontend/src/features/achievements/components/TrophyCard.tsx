import { Link } from 'react-router';
import { ShareCard } from '../../share/ShareCard';
import { trophyFilename } from '../../share/filenames';
import { useRoundTypeLink } from '../../../lib/roundTypes';
import type { components } from '../../../api/schema';
import { formatPct } from '../labels';
import { TrophyIcon } from './TrophyIcon';

type TrophyOut = components['schemas']['TrophyOut'];

export function TrophyCard({ trophy }: { trophy: TrophyOut }) {
  const to = useRoundTypeLink(`/achievements/${encodeURIComponent(trophy.code)}`);
  const card = (
    <Link to={to} className="flex min-h-11 items-center gap-3 rounded-xl bg-elevated p-3">
      <TrophyIcon
        artKey={trophy.art_key}
        metal={trophy.metal}
        locked={trophy.holders === 0}
        size={56}
      />
      <span className="flex flex-col">
        <span className="font-medium">{trophy.name}</span>
        {trophy.label === null ? null : (
          <span className="text-sm text-text-muted">{trophy.label}</span>
        )}
        <span className="text-xs text-text-muted">
          {trophy.holders} {trophy.holders === 1 ? 'holder' : 'holders'} ·{' '}
          {formatPct(trophy.rarity_pct)}
        </span>
      </span>
    </Link>
  );
  // A trophy nobody has earned yet is not worth sharing.
  if (trophy.holders === 0) return card;
  return (
    <ShareCard
      compact
      filename={trophyFilename(trophy.code)}
      name={trophy.label === null ? trophy.name : `${trophy.name}, ${trophy.label}`}
    >
      {card}
    </ShareCard>
  );
}
