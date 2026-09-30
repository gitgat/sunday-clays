import type { EventSection } from '../events/sections';
import { SundayInsights } from './components/FeedSections';

export const eventSection: EventSection = {
  id: 'insights',
  title: 'Insights',
  order: 0,
  placement: 'top',
  bare: true,
  Component: SundayInsights,
};
