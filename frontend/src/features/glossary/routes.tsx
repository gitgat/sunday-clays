import { BookOpen } from 'lucide-react';
import type { RouteObject } from 'react-router';
import type { NavItem } from '../../app/registry';
import { FeatureGate } from '../../components/FeatureGate';
import { NO_FILTERS } from '../../lib/pageFilters';

export const routes: RouteObject[] = [
  {
    path: '/glossary',
    handle: { filters: NO_FILTERS },
    lazy: async () => {
      const { GlossaryPage } = await import('./pages/GlossaryPage');
      return {
        element: (
          <FeatureGate feature="tour_glossary">
            <GlossaryPage />
          </FeatureGate>
        ),
      };
    },
  },
];

export const nav: NavItem[] = [
  { label: 'Glossary', path: '/glossary', icon: BookOpen, order: 135, feature: 'tour_glossary' },
];
