import { screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../test/msw/server';
import { renderRoutes } from '../../test/render';
import { meta } from './mocks';
import { nav, routes } from './routes';

/**
 * A root route with HydrateFallback mirrors app/router.tsx, so the lazy children load without React
 * Router's "no HydrateFallback" warning.
 */
function renderAt(route: string) {
  return renderRoutes([{ path: '/', HydrateFallback: () => null, children: routes }], { route });
}

// These tests use this feature's default handlers (./mocks, merged into the global MSW server) on purpose.
describe('events routes', () => {
  it('serve the season page at /events', async () => {
    server.use(http.get('*/api/meta', () => HttpResponse.json(meta))); // /api/meta's default handler is home's
    renderAt('/events');
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Sundays 2026' }),
    ).toBeInTheDocument();
    const list = await screen.findByRole('list', { name: 'Sundays in 2026' });
    expect(within(list).getAllByRole('listitem')).toHaveLength(4);
  });

  it('serve the event page at /events/:date', async () => {
    renderAt('/events/2026-09-13');
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Sep 13, 2026' }),
    ).toBeInTheDocument();
  });

  it('register Events as a mobile tab at nav order 20', () => {
    expect(nav).toEqual([
      expect.objectContaining({ label: 'Events', path: '/events', order: 20, mobileTab: true }),
    ]);
  });
});
