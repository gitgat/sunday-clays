import { useId, useState } from 'react';
import type { Explainer } from '../../../components/charts/types';
import { ExplainerPanel, ExplainerToggle, ScopeTag } from '../../../components/ui/Explainer';

/** The "About …" disclosure for a card that is not a ChartFrame (the calendar, the results table). */
export function About({
  explainer,
  label = 'About this chart',
}: {
  explainer: Explainer;
  label?: string;
}) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  return (
    <>
      <div className="mb-1 flex flex-wrap items-center gap-2">
        <ExplainerToggle
          label={label}
          panelId={panelId}
          open={open}
          onToggle={() => setOpen((v) => !v)}
        />
        <ScopeTag scope={explainer.scope} />
      </div>
      {open && <ExplainerPanel id={panelId} explainer={explainer} />}
    </>
  );
}
