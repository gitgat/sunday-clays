import { describe, expect, it } from 'vitest';

import { RecordsPage } from './pages/RecordsPage';
import { nav, routes } from './routes';

describe('records routes', () => {
  it('lazily loads RecordsPage at /records', async () => {
    const [route] = routes;
    expect(route?.path).toBe('/records');
    if (typeof route?.lazy !== 'function') throw new Error('expected a lazy route function');
    await expect(route.lazy()).resolves.toMatchObject({ Component: RecordsPage });
  });

  it('registers Records in the nav at order 120', () => {
    expect(nav).toEqual([
      expect.objectContaining({ label: 'Records', path: '/records', order: 120 }),
    ]);
  });
});
