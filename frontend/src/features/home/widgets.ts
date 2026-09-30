import type { FC } from 'react';

/**
 * Extension point (C10): a feature exports `homeWidget` from `src/features/<name>/homeWidget.tsx`. `hero` widgets
 * render full width under the page title (Plan 12); `main` widgets render in the main column with `meId` (possibly
 * null); `me` widgets render inside the me panel once a me profile has loaded.
 */
export type HomeWidget = {
  id: string;
  order: number;
  slot: 'hero' | 'main' | 'me';
  Component: FC<{ meId: number | null }>;
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
