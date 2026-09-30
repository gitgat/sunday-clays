import type { HomeWidget } from '../home/widgets';
import { OnThisDayCard } from './components/OnThisDayCard';

/** C10 home widget: "On this day" in the main column. */
export const homeWidget: HomeWidget = {
  id: 'on-this-day',
  order: 40,
  slot: 'main',
  Component: OnThisDayCard,
};
