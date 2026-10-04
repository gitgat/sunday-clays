import type { HomeWidget } from '../home/widgets';
import { ComingUpCard } from './components/ComingUpCard';

/** C10 home widget (§5.7.4): after Next Sunday (10), before On this day (40); insights stay in the hero. */
export const homeWidget: HomeWidget = {
  id: 'club-events-next',
  order: 15,
  slot: 'main',
  Component: ComingUpCard,
};
