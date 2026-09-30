import { describe, expect, it } from 'vitest';

import { RacePage } from './pages/RacePage';
import { routes } from './routes';

describe('race routes', () => {
  it('lazily loads RacePage at /race', async () => {
    const [route] = routes;
    expect(route?.path).toBe('/race');
    if (typeof route?.lazy !== 'function') throw new Error('expected a lazy route function');
    await expect(route.lazy()).resolves.toMatchObject({ Component: RacePage });
  });
});
