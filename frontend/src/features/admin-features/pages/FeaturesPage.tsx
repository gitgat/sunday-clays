import { useId, useState } from 'react';
import { Card } from '../../../components/ui/Card';
import { Toggle } from '../../../components/ui/Toggle';
import {
  useFeatureSwitches,
  usePageCacheStatus,
  useSetFeatureSwitch,
  type FeatureSwitch,
} from '../api';
import { cacheStatusText, changedText, FEATURES_INTRO, INFRA_INTRO } from '../copy';

function SwitchRow({
  row,
  onChange,
  pending,
  status,
  locked = false,
}: {
  row: FeatureSwitch;
  onChange: (enabled: boolean) => void;
  pending: boolean;
  status?: string;
  locked?: boolean;
}) {
  const statusId = useId();
  return (
    <li className="flex flex-col gap-1 border-b border-outline-variant py-3 last:border-b-0">
      <Toggle
        label={row.label}
        checked={row.enabled}
        onChange={onChange}
        disabled={pending || locked}
        describedBy={status === undefined ? undefined : statusId}
      />
      <p className="text-sm text-text-muted">{row.description}</p>
      <p className="text-xs text-text-muted">{changedText(row.updated_on)}</p>
      {status !== undefined && (
        <p id={statusId} className="text-xs text-text-muted">
          {status}
        </p>
      )}
    </li>
  );
}

/** Admin page: one launch switch per feature (Plan 19 §3.0). */
export function FeaturesPage() {
  const query = useFeatureSwitches();
  const mutation = useSetFeatureSwitch();
  const cache = usePageCacheStatus();
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
      {failed === null ? null : (
        <p role="alert" className="text-sm text-text">
          {failed}
        </p>
      )}
      {query.isPending ? (
        <p role="status">Loading switches…</p>
      ) : query.isError ? (
        <p role="alert">Could not load the switches.</p>
      ) : (
        <>
          <Card title="Launch switches">
            <ul className="flex flex-col">
              {query.data
                .filter((row) => row.kind === 'feature')
                .map((row) => (
                  <SwitchRow
                    key={row.key}
                    row={row}
                    pending={mutation.isPending}
                    onChange={(enabled) => change(row, enabled)}
                  />
                ))}
            </ul>
          </Card>
          <Card title="Infrastructure" subtitle={INFRA_INTRO}>
            <ul className="flex flex-col">
              {query.data
                .filter((row) => row.kind === 'infrastructure')
                .map((row) => (
                  <SwitchRow
                    key={row.key}
                    row={row}
                    pending={mutation.isPending}
                    locked={row.key === 'page_cache' && cache.data?.forced_off === true}
                    status={
                      row.key !== 'page_cache'
                        ? undefined
                        : cache.data
                          ? cacheStatusText(cache.data)
                          : 'Status unavailable'
                    }
                    onChange={(enabled) => change(row, enabled)}
                  />
                ))}
            </ul>
          </Card>
        </>
      )}
    </div>
  );
}
