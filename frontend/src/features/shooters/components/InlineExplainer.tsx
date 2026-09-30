import { useId, useState } from 'react';
import type { Explainer } from '../../../components/charts/types';
import { ExplainerPanel, ExplainerToggle, ScopeTag } from '../../../components/ui/Explainer';

/** An "About …" disclosure for a table or strip that is not a ChartFrame. */
export function InlineExplainer({ label, explainer }: { label: string; explainer: Explainer }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  return (
    <div className="flex flex-col">
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
    </div>
  );
}

/** Says a stat or chart ignores the global round-type filter (so it can differ from the hero). */
export function AllRoundTypesTag() {
  return (
    <span className="rounded-button border border-outline-variant px-2 py-0.5 text-xs text-text-muted">
      All round types
    </span>
  );
}
