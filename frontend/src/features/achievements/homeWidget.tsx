import type { HomeWidget } from '../home/widgets';
import { NextTrophy } from './NextTrophy';

export const homeWidget: HomeWidget = {
  id: 'next-trophy',
  order: 30,
  slot: 'me',
  Component: NextTrophy,
};
