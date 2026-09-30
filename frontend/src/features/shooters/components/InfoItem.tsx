import { useId, useState, type ReactNode } from 'react';
import type { Explainer } from '../../../components/charts/types';
import { cx } from '../../../components/ui/cx';
import { ExplainerPanel, ExplainerToggle, ScopeTag } from '../../../components/ui/Explainer';

export function InfoItem({
  label,
  value,
  hint,
  className,
  explainer,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  className?: string;
  /** A "?" beside the label; the item spans the whole row while its panel is open. */
  explainer?: Explainer;
}) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  return (
    <div className={cx('flex min-w-0 flex-col', className, open && 'col-span-2 lg:col-span-4')}>
      <dt className="flex items-center justify-between gap-2 text-xs text-text-muted">
        {label}
        {explainer !== undefined && (
          <ExplainerToggle
            compact
            label={`About ${label}`}
            panelId={panelId}
            open={open}
            onToggle={() => setOpen((v) => !v)}
          />
        )}
      </dt>
      <dd className="text-lg tabular-nums">{value}</dd>
      {hint && <dd className="text-xs text-text-muted">{hint}</dd>}
      {explainer?.scope !== undefined && (
        <dd className="flex">
          <ScopeTag scope={explainer.scope} />
        </dd>
      )}
      {explainer !== undefined && open && (
        <dd className="mt-2">
          <ExplainerPanel id={panelId} explainer={explainer} />
        </dd>
      )}
    </div>
  );
}
