import { useId, useState } from 'react';
import type { Explainer } from '../charts/types';
import { ExplainerPanel, ExplainerToggle, ScopeTag } from './Explainer';

/** "About this table": the same disclosure ChartFrame shows, for a table that is not a chart. */
export function AboutBlock({
  explainer,
  label = 'About this table',
}: {
  explainer: Explainer | undefined;
  label?: string;
}) {
  const panelId = useId();
  const [open, setOpen] = useState(false);
  if (explainer === undefined) return null;
  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <ExplainerToggle
          label={label}
          panelId={panelId}
          open={open}
          onToggle={() => {
            setOpen((v) => !v);
          }}
        />
        <ScopeTag scope={explainer.scope} />
      </div>
      {open && <ExplainerPanel id={panelId} explainer={explainer} />}
    </div>
  );
}
