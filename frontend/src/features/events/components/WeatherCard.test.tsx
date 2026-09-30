import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import { eventDetail } from '../mocks';
import { compass, WeatherCard } from './WeatherCard';

describe('compass', () => {
  it.each([
    [0, 'N'],
    [44, 'NE'],
    [180, 'S'],
    [225, 'SW'],
    [350, 'N'],
    [-10, 'N'],
  ])('%d° → %s', (deg, want) => {
    expect(compass(deg)).toBe(want);
  });
});

describe('WeatherCard', () => {
  it('shows the event-window weather in °F, mph, inches and inHg', () => {
    renderWithProviders(<WeatherCard weather={eventDetail.weather} />);
    expect(screen.getByText('Partly cloudy')).toBeInTheDocument();
    expect(screen.getByText('58°F (feels 57°F)')).toBeInTheDocument();
    expect(screen.getByText('6 mph SW, gusts 12 mph')).toBeInTheDocument();
    expect(screen.getByText('0.00 in')).toBeInTheDocument();
    expect(screen.getByText('40%')).toBeInTheDocument();
    expect(screen.getByText('71%')).toBeInTheDocument();
    expect(screen.getByText(/30\.01/)).toBeInTheDocument();
  });

  it('renders missing fields as dashes', () => {
    renderWithProviders(
      <WeatherCard
        weather={{
          temp_f: null,
          apparent_f: null,
          precip_in: null,
          wind_mph: null,
          gust_mph: null,
          wind_dir_deg: null,
          cloud_pct: null,
          humidity_pct: null,
          pressure_hpa: null,
          condition: 'drizzle',
        }}
      />,
    );
    expect(screen.getByText('drizzle')).toBeInTheDocument();
    expect(screen.getByText('— (feels —)')).toBeInTheDocument();
    expect(screen.getAllByText('—')).toHaveLength(5);
  });

  it('shows wind without a direction when the direction is missing', () => {
    const weather = eventDetail.weather;
    if (!weather) throw new Error('fixture has weather');
    renderWithProviders(
      <WeatherCard weather={{ ...weather, wind_dir_deg: null, condition: null }} />,
    );
    expect(screen.getByText('6 mph, gusts 12 mph')).toBeInTheDocument();
  });

  it('shows an empty state when the event has no weather', () => {
    renderWithProviders(<WeatherCard weather={null} />);
    expect(screen.getByText('No weather recorded for this Sunday')).toBeInTheDocument();
  });
});
