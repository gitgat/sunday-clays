import { describe, expect, it } from 'vitest';

import { LeaderboardsPage } from './pages/LeaderboardsPage';
import { routes } from './routes';

describe('leaderboards routes', () => {
  it('lazily loads LeaderboardsPage at /leaderboards', async () => {
    const [route] = routes;
    expect(route?.path).toBe('/leaderboards');
    if (typeof route?.lazy !== 'function') throw new Error('expected a lazy route function');
    await expect(route.lazy()).resolves.toMatchObject({ Component: LeaderboardsPage });
  });
});
