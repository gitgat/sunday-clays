import type { HomeWidget } from '../home/widgets';
import { HomeInsights } from './components/FeedSections';

export const homeWidget: HomeWidget = {
  id: 'insights',
  order: 0,
  slot: 'hero',
  Component: HomeInsights,
};
