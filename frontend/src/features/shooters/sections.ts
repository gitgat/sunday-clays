import type { FC } from 'react';

/** Extension point (C10): a feature exports `profileSection` from `src/features/<name>/profileSection.tsx`. */
export type ProfileSection = {
  id: string;
  title: string;
  order: number;
  /** 'top' renders under the hero and odometer, above the Stats card (Plan 12); default 'bottom'. */
  placement?: 'top' | 'bottom';
  /** The component renders its own card, or nothing (Plan 12 insights stay silent when empty). */
  bare?: boolean;
  Component: FC<{ shooterId: number }>;
};

type SectionModule = { profileSection?: ProfileSection };

export function collectProfileSections(modules: Record<string, SectionModule>): ProfileSection[] {
  return Object.values(modules)
    .flatMap((m) => (m.profileSection ? [m.profileSection] : []))
    .sort((a, b) => a.order - b.order || a.id.localeCompare(b.id));
}

/** The sections for one place on the page, in order. */
export function sectionsAt(
  sections: readonly ProfileSection[],
  placement: 'top' | 'bottom',
): ProfileSection[] {
  return sections.filter((s) => (s.placement ?? 'bottom') === placement);
}

export const profileSections: ProfileSection[] = collectProfileSections(
  import.meta.glob<SectionModule>('../*/profileSection.tsx', { eager: true }),
);
