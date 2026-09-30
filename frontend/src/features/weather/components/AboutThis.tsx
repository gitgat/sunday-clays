import { useId, useState } from 'react';
import type { Explainer } from '../../../components/charts/types';
import { ExplainerPanel, ExplainerToggle, ScopeTag } from '../../../components/ui/Explainer';

/** The "About" disclosure and scope tag for a block that is not a ChartFrame or a Stat. */
export function AboutThis({ label, explainer }: { label: string; explainer: Explainer }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
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
