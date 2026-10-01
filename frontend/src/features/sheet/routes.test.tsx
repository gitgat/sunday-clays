import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { LAZY_CHART } from '../../test/lazyChart';
import { server } from '../../test/msw/server';
import { renderRoutes } from '../../test/render';
import { sheetFixture } from './mocks';
import { nav, routes } from './routes';

function renderAt(route: string) {
  return renderRoutes([{ path: '/', HydrateFallback: () => null, children: routes }], { route });
}

describe('sheet routes', () => {
  it('serve the latest issue at /', async () => {
    const asked: string[] = [];
    server.use(
      http.get('*/api/sheet/latest', () => {
        asked.push('latest');
        return HttpResponse.json(sheetFixture());
      }),
    );
    renderAt('/');
    expect(
      await screen.findByRole('heading', { level: 1, name: 'The Sunday Sheet' }, LAZY_CHART),
    ).toBeInTheDocument();
    expect(asked).toEqual(['latest']);
  });

  it('serve an issue at /sheet/:date', async () => {
    const asked: string[] = [];
    server.use(
      http.get('*/api/sheet/:date', ({ request }) => {
        asked.push(new URL(request.url).pathname);
        return HttpResponse.json(sheetFixture());
      }),
    );
    renderAt('/sheet/2026-09-27');
    expect(
      await screen.findByRole('heading', { level: 1, name: 'The Sunday Sheet' }, LAZY_CHART),
    ).toBeInTheDocument();
    expect(asked).toEqual(['/api/sheet/2026-09-27']);
  });

  it('are the first nav item and a phone tab', () => {
    expect(nav).toEqual([
      expect.objectContaining({ label: 'Sheet', path: '/', order: 10, mobileTab: true }),
    ]);
  });
});
