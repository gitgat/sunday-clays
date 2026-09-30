import { useId, useState } from 'react';
import type { ReactNode } from 'react';
import { AdminError } from '../../admin/components/AdminError';
import { useEventResults } from '../api';
import type { RoundRef } from '../rules';
import { TextField } from './Fields';

/** Picks one round (event_date, name_key, ordinal) from an event's results — C5 score_override/hide_round targets. */
export function RoundPicker({
  value,
  onChange,
}: {
  value: RoundRef | null;
  onChange: (round: RoundRef | null) => void;
}) {
  const [date, setDate] = useState('');
  const event = useEventResults(date);
  const groupName = useId();

  let body: ReactNode = null;
  if (date !== '') {
    if (event.isPending) body = <p className="text-sm text-text-muted">Loading results…</p>;
    else if (event.isError) body = <AdminError error={event.error} />;
    else if (event.data.results.length === 0)
      body = <p className="text-sm text-text-muted">No rounds on this date.</p>;
    else {
      const sorted = [...event.data.results].sort(
        (a, b) =>
          b.score - a.score ||
          a.display_name.localeCompare(b.display_name) ||
          a.ordinal - b.ordinal,
      );
      body = (
        <fieldset className="flex flex-col gap-1">
          <legend className="text-sm">Round</legend>
          {sorted.map((r) => (
            <label
              key={r.round_id}
              className="flex min-h-11 items-center gap-2 [overflow-wrap:anywhere]"
            >
              <input
                type="radio"
                name={groupName}
                checked={value?.name_key === r.name_key && value.ordinal === r.ordinal}
                onChange={() =>
                  onChange({
                    event_date: date,
                    name_key: r.name_key,
                    ordinal: r.ordinal,
                    display_name: r.display_name,
                    score: r.score,
                  })
                }
              />
              {`${r.display_name} — ${r.score}${r.ordinal > 1 ? ` (round ${r.ordinal})` : ''}`}
            </label>
          ))}
        </fieldset>
      );
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <TextField
        label="Event date"
        type="date"
        value={date}
        onChange={(next) => {
          setDate(next);
          onChange(null);
        }}
      />
      {body}
    </div>
  );
}
