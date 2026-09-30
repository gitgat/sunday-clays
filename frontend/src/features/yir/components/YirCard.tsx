import { useId, useState, type ReactNode } from 'react';
import type { Explainer } from '../../../components/charts/types';
import { Card } from '../../../components/ui/Card';
import { ExplainerPanel, ExplainerToggle } from '../../../components/ui/Explainer';
import { ShareCard } from '../../share/ShareCard';
import { cardFilename } from '../../share/filenames';

/**
 * A titled Year in Review card (a region named `title`) with an "About this card" disclosure that
 * says what its numbers are and how they are worked out. It is shareable as an image
 * (without the disclosure, which is marked `data-share-exclude`).
 */
export function YirCard({
  title,
  explainer,
  children,
}: {
  title: string;
  explainer: Explainer;
  children: ReactNode;
}) {
  const panelId = useId();
  const [open, setOpen] = useState(false);
  return (
    <ShareCard filename={cardFilename(title)} name={title}>
      <Card title={title} className="min-w-0">
        <div className="mb-2" data-share-exclude>
          <ExplainerToggle
            label="About this card"
            panelId={panelId}
            open={open}
            onToggle={() => setOpen((v) => !v)}
          />
        </div>
        {open && (
          <div className="mb-3" data-share-exclude>
            <ExplainerPanel id={panelId} explainer={explainer} />
          </div>
        )}
        <div className="flex flex-col gap-2">{children}</div>
      </Card>
    </ShareCard>
  );
}
