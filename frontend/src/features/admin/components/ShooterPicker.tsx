import { useDeferredValue, useId, useState } from 'react';
import type { ReactNode } from 'react';
import { Button } from '../../../components/ui/Button';
import { useShooterSearch } from '../api';
import type { ShooterOption } from '../api';
import { AdminError } from './AdminError';

export function ShooterPicker({
  label,
  value,
  onChange,
}: {
  label: string;
  value: ShooterOption | null;
  onChange: (value: ShooterOption | null) => void;
}) {
  const id = useId();
  const [q, setQ] = useState('');
  const term = useDeferredValue(q.trim());
  const results = useShooterSearch(term);

  if (value !== null) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-text-muted">{`${label}:`}</span>
        <strong>{value.display_name}</strong>
        <span className="text-xs text-text-muted">{`#${value.shooter_id}`}</span>
        <Button type="button" variant="ghost" onClick={() => onChange(null)}>
          Change
        </Button>
      </div>
    );
  }

  let matches: ReactNode = null;
  if (term.length >= 2) {
    if (results.isPending) matches = <p className="text-sm text-text-muted">Searching…</p>;
    else if (results.isError) matches = <AdminError error={results.error} />;
    else if (results.data.length === 0)
      matches = <p className="text-sm text-text-muted">No shooters match</p>;
    else
      matches = (
        <ul aria-label={`${label} matches`} className="flex flex-col">
          {results.data.slice(0, 8).map((s) => (
            <li key={s.shooter_id}>
              <button
                type="button"
                className="min-h-11 w-full px-2 text-left"
                onClick={() => onChange({ shooter_id: s.shooter_id, display_name: s.display_name })}
              >
                {`${s.display_name} · ${s.n_rounds} rounds`}
              </button>
            </li>
          ))}
        </ul>
      );
  }

  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm">
        {label}
      </label>
      <input
        id={id}
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        className="min-h-11 rounded-button border border-outline-variant bg-elevated px-3"
      />
      {matches}
    </div>
  );
}
