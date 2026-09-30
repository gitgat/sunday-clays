import type { FC } from 'react';

/** Extension point (C10): a feature exports `eventSection` from `src/features/<name>/eventSection.tsx`. */
export type EventSection = {
  id: string;
  title: string;
  order: number;
  /** 'top' renders under the page header, above the results (Plan 12); default 'bottom'. */
  placement?: 'top' | 'bottom';
  /** The component renders its own card, or nothing (Plan 12 insights stay silent when empty). */
  bare?: boolean;
  Component: FC<{ date: string }>;
};

type SectionModule = { eventSection?: EventSection };

export function collectEventSections(modules: Record<string, SectionModule>): EventSection[] {
  return Object.values(modules)
    .flatMap((m) => (m.eventSection ? [m.eventSection] : []))
    .sort((a, b) => a.order - b.order || a.id.localeCompare(b.id));
}

/** The sections for one place on the page, in order. */
export function sectionsAt(
  sections: readonly EventSection[],
  placement: 'top' | 'bottom',
): EventSection[] {
  return sections.filter((s) => (s.placement ?? 'bottom') === placement);
}

export const eventSections: EventSection[] = collectEventSections(
  import.meta.glob<SectionModule>('../*/eventSection.tsx', { eager: true }),
);
