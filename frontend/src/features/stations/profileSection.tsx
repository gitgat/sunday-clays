import type { ProfileSection } from '../shooters/sections';
import { StationBreakdown } from './StationBreakdown';

export const profileSection: ProfileSection = {
  id: 'stations',
  title: 'Stations',
  order: 70,
  Component: StationBreakdown,
};
