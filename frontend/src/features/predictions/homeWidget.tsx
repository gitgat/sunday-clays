import type { HomeWidget } from '../home/widgets';
import { NextSundayCard } from './components/NextSundayCard';

/** C10 home widget: the "Next Sunday" card in the main column. */
export const homeWidget: HomeWidget = {
  id: 'next-sunday',
  order: 10,
  slot: 'main',
  Component: NextSundayCard,
};
