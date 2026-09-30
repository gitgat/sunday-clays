import { widgetsForSlot } from '../widgets';
import type { HomeWidget } from '../widgets';

/** Renders a slot's widgets in order; each widget renders itself (no wrapper card, D5). */
export function WidgetSlot({
  slot,
  widgets,
  meId,
}: {
  slot: HomeWidget['slot'];
  widgets: HomeWidget[];
  meId: number | null;
}) {
  return (
    <>
      {widgetsForSlot(widgets, slot).map(({ id, Component }) => (
        <Component key={id} meId={meId} />
      ))}
    </>
  );
}
