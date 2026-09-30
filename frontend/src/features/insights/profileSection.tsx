import type { ProfileSection } from '../shooters/sections';
import { ProfileInsights } from './components/FeedSections';

export const profileSection: ProfileSection = {
  id: 'insights',
  title: 'Insights',
  order: 0,
  placement: 'top',
  bare: true,
  Component: ProfileInsights,
};
