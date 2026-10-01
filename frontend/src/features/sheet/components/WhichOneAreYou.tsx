import { useId, useState } from 'react';
import { Button } from '../../../components/ui/Button';
import { Card } from '../../../components/ui/Card';
import { setMe, skipMe } from '../../../lib/me';
import { useShooters } from '../../shooters/api';

const MIN_QUERY = 2;
const SHOWN = 8;

/**
 * "Which one are you?" (Plan 14): pick yourself once and this browser remembers it (lib/me), or
 * skip. No modal, no tour; nothing is sent anywhere but the name search.
 */
export function WhichOneAreYou({
  onPicked,
  onSkipped,
}: {
  onPicked: (id: number) => void;
  onSkipped: () => void;
}) {
  const inputId = useId();
  const [q, setQ] = useState('');
  const query = q.trim();
  const asked = query.length >= MIN_QUERY;
  const search = useShooters(query, false, { enabled: asked });
  const found = asked ? (search.data ?? []) : [];
  const matches = found.slice(0, SHOWN);
  return (
    <Card title="Which one are you?" subtitle="Pick your name once; this browser remembers it.">
      <div className="flex flex-col gap-3">
        <label htmlFor={inputId} className="text-sm text-text-muted">
          Your name
        </label>
        <input
          id={inputId}
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          autoComplete="off"
          className="min-h-11 rounded-button border border-outline-variant bg-surface px-3 text-text"
        />
        <div role="status" className="empty:hidden">
          {asked && search.isError && (
            <p className="text-sm text-text-muted">Couldn’t search the shooters just now.</p>
          )}
          {asked && search.isSuccess && matches.length === 0 && (
            <p className="text-sm text-text-muted">{`No shooter matches “${query}”.`}</p>
          )}
          {matches.length > 0 && (
            <p className="text-sm text-text-muted">
              {found.length > matches.length
                ? `Showing ${String(matches.length)} of ${String(found.length)} matches`
                : `${String(matches.length)} ${matches.length === 1 ? 'match' : 'matches'}`}
            </p>
          )}
        </div>
        {matches.length > 0 && (
          <ul aria-label="Matching shooters" className="flex flex-col gap-2">
            {matches.map((s) => (
              <li key={s.shooter_id}>
                <Button
                  variant="tonal"
                  className="w-full justify-start"
                  onClick={() => {
                    setMe(s.shooter_id);
                    onPicked(s.shooter_id);
                  }}
                >
                  {s.display_name}
                </Button>
              </li>
            ))}
          </ul>
        )}
        <Button
          variant="ghost"
          className="self-start"
          onClick={() => {
            skipMe();
            onSkipped();
          }}
        >
          Not a shooter / skip
        </Button>
      </div>
    </Card>
  );
}
