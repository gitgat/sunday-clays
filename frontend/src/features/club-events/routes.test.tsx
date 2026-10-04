import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../test/msw/server';
import { renderRoutes } from '../../test/render';
import { nav, routes } from './routes';

describe('club-events routes (§5.7.1, D1)', () => {
  it('adds "Club events" to the nav at 25 behind the events switch, not as a tab', () => {
    expect(nav).toEqual([
      expect.objectContaining({
        label: 'Club events',
        path: '/club-events',
        order: 25,
        feature: 'events',
      }),
    ]);
    expect(nav[0]?.mobileTab).toBeUndefined();
  });

  it('declares no filters on either page', () => {
    for (const route of routes) {
      expect(route.handle).toEqual({ filters: { roundType: false, window: false } });
    }
  });

  it('shows a viewer the not-found page while the switch is off', async () => {
    server.use(http.get('*/api/features', () => HttpResponse.json({ switches: {} })));
    renderRoutes(routes, { route: '/club-events' });
    expect(await screen.findByText('Page not found')).toBeInTheDocument();
  });

  it('shows the page once the switch is on', async () => {
    server.use(http.get('*/api/features', () => HttpResponse.json({ switches: { events: true } })));
    renderRoutes(routes, { route: '/club-events/1' });
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Fall Fun Shoot' }),
    ).toBeInTheDocument();
  });
});
