import { useState } from 'react';
import { Card } from '../../../components/ui/Card';
import { Toggle } from '../../../components/ui/Toggle';
import { useFeatureSwitches, useSetFeatureSwitch, type FeatureSwitch } from '../api';
import { changedText, FEATURES_INTRO } from '../copy';

function SwitchRow({
  row,
  onChange,
  pending,
}: {
  row: FeatureSwitch;
  onChange: (enabled: boolean) => void;
  pending: boolean;
}) {
  return (
    <li
      aria-label={row.label}
      className="flex flex-col gap-1 border-b border-outline-variant py-3 last:border-b-0"
    >
      <Toggle label={row.label} checked={row.enabled} onChange={onChange} disabled={pending} />
      <p className="text-sm text-text-muted">{row.description}</p>
      <p className="text-xs text-text-muted">{changedText(row.updated_on)}</p>
    </li>
  );
}

/** Admin page: one launch switch per feature (Plan 19 §3.0). */
export function FeaturesPage() {
  const query = useFeatureSwitches();
  const mutation = useSetFeatureSwitch();
  const [failed, setFailed] = useState<string | null>(null);
  const change = (row: FeatureSwitch, enabled: boolean) => {
    setFailed(null);
    mutation.mutate(
      { key: row.key, enabled },
      { onError: () => setFailed(`Could not change ${row.label}. Try again.`) },
    );
  };
  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-medium">Features</h1>
        <p className="text-text-muted">{FEATURES_INTRO}</p>
      </header>
      <p aria-live="polite" className="text-sm text-text-muted">
        {failed ?? ''}
      </p>
      {query.isPending ? (
        <p role="status">Loading switches…</p>
      ) : query.isError ? (
        <p role="alert">Could not load the switches.</p>
      ) : (
        <Card title="Launch switches">
          <ul className="flex flex-col">
            {query.data.map((row) => (
              <SwitchRow
                key={row.key}
                row={row}
                pending={mutation.isPending}
                onChange={(enabled) => change(row, enabled)}
              />
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
