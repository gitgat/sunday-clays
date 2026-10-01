import type { FC } from 'react';
import type { SheetIssue } from '../sheet/api';

/**
 * What a widget gets: the viewer's "me" id (possibly null) and, on the Sunday Sheet, the issue
 * being shown (Plan 14).
 */
export type HomeWidgetProps = { meId: number | null; issue?: SheetIssue };

/**
 * Extension point (C10): a feature exports `homeWidget` from `src/features/<name>/homeWidget.tsx`.
 * On the Sunday Sheet (Plan 14) `hero` widgets are the lead (the headline and the spotlight),
 * `main` widgets are rail cards (shown on the latest issue), and `me` widgets render inside
 * "Your Sunday" once a me profile has loaded.
 */
export type HomeWidget = {
  id: string;
  order: number;
  slot: 'hero' | 'main' | 'me';
  Component: FC<HomeWidgetProps>;
};

type WidgetModule = { homeWidget?: HomeWidget };

export function collectHomeWidgets(modules: Record<string, WidgetModule>): HomeWidget[] {
  return Object.values(modules)
    .flatMap((m) => (m.homeWidget ? [m.homeWidget] : []))
    .sort((a, b) => a.order - b.order || a.id.localeCompare(b.id));
}

export function widgetsForSlot(widgets: HomeWidget[], slot: HomeWidget['slot']): HomeWidget[] {
  return widgets.filter((w) => w.slot === slot);
}

export const homeWidgets: HomeWidget[] = collectHomeWidgets(
  import.meta.glob<WidgetModule>('../*/homeWidget.tsx', { eager: true }),
);
