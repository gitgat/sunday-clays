import { screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { expectExplainer } from '../../../test/charts';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { WEATHER_SENSITIVITY } from '../mocks';
import { WeatherSensitivityCard } from './WeatherSensitivityCard';

describe('WeatherSensitivityCard', () => {
  it("lists the shooter's shrunk effects in natural units", async () => {
    server.use(http.get('*/api/weather/sensitivity', () => HttpResponse.json(WEATHER_SENSITIVITY)));
    renderWithProviders(<WeatherSensitivityCard shooterId={59} />);
    const card = screen.getByRole('region', { name: 'Weather effects on this shooter' });
    expect(
      await within(card).findByText('Temperature: +0.3 targets per 10 °F warmer'),
    ).toBeInTheDocument();
    expect(
      within(card).getByText('Wind gusts: −0.6 targets per 10 mph more gust'),
    ).toBeInTheDocument();
    expect(within(card).getByText('Rain: not enough variety to tell')).toBeInTheDocument();
    expect(within(card).getByText(/Based on 78 rounds with weather/)).toBeInTheDocument();
  });

  it('explains the numbers and says they cover all history', async () => {
    server.use(http.get('*/api/weather/sensitivity', () => HttpResponse.json(WEATHER_SENSITIVITY)));
    renderWithProviders(<WeatherSensitivityCard shooterId={59} />);
    const card = screen.getByRole('region', { name: 'Weather effects on this shooter' });
    await within(card).findByText(/Based on 78 rounds/);
    expect(within(card).getByText('All time')).toBeInTheDocument();
    expect(within(card).getByText('All round types')).toBeVisible();
    await expectExplainer(card, 'About weather sensitivity', { read: true });
  });

  it('says when the shooter has too few rounds with weather', async () => {
    server.use(http.get('*/api/weather/sensitivity', () => HttpResponse.json(WEATHER_SENSITIVITY)));
    renderWithProviders(<WeatherSensitivityCard shooterId={7} />);
    expect(
      await screen.findByText(
        'Not enough rounds with weather yet. This needs 10 rounds with a weather record.',
      ),
    ).toBeInTheDocument();
  });

  it('reports a failed request', async () => {
    server.use(
      http.get('*/api/weather/sensitivity', () =>
        HttpResponse.json({ error: { code: 'internal', message: 'x' } }, { status: 500 }),
      ),
    );
    renderWithProviders(<WeatherSensitivityCard shooterId={59} />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load weather effects.');
  });
});
