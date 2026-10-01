import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderRoutes } from '../../test/render';
import { routes } from './routes';

describe('sheet routes', () => {
  it('serve an issue at /sheet/:date', async () => {
    renderRoutes([{ path: '/', HydrateFallback: () => null, children: routes }], {
      route: '/sheet/2026-09-27',
    });
    expect(
      await screen.findByRole('heading', { level: 1, name: 'The Sunday Sheet' }),
    ).toBeInTheDocument();
  });
});
