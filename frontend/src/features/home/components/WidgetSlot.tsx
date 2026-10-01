import type { SheetIssue } from '../../sheet/api';
import { widgetsForSlot } from '../widgets';
import type { HomeWidget } from '../widgets';

/** Renders a slot's widgets in order; each widget renders itself (no wrapper card, D5). */
export function WidgetSlot({
  slot,
  widgets,
  meId,
  issue,
}: {
  slot: HomeWidget['slot'];
  widgets: HomeWidget[];
  meId: number | null;
  /** The Sunday Sheet's issue, for widgets that show part of it (Plan 14). */
  issue?: SheetIssue;
}) {
  return (
    <>
      {widgetsForSlot(widgets, slot).map(({ id, Component }) => (
        <Component key={id} meId={meId} issue={issue} />
      ))}
    </>
  );
}
