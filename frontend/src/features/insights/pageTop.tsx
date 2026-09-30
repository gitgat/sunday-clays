import type { PageTop } from '../../components/layout/pageTop';
import { PageInsights } from './components/FeedSections';

/** Insights under the title of the club, leaderboards, records and stations pages (Plan 12). */
export const pageTop: PageTop = {
  id: 'insights',
  order: 0,
  pages: ['club', 'leaderboards', 'records', 'stations'],
  Component: PageInsights,
};
