import type { EventSection } from '../events/sections';
import { TrophiesToday } from './TrophiesToday';

export const eventSection: EventSection = {
  id: 'trophies-today',
  title: 'Trophies earned today',
  order: 60,
  Component: TrophiesToday,
};
