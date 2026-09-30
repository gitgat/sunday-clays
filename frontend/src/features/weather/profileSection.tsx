import type { ProfileSection } from '../shooters/sections';
import { WeatherSensitivityCard } from './components/WeatherSensitivityCard';

/** C10 profile section: this shooter's weather sensitivity. */
export const profileSection: ProfileSection = {
  id: 'weather',
  title: 'Weather sensitivity',
  order: 50,
  Component: WeatherSensitivityCard,
};
