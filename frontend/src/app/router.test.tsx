import { screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from 'vitest';

import { LAZY_CHART } from '../test/lazyChart';
import { renderRoute } from '../test/render';
import { appRoutes, createAppRouter } from './router';

describe('app router', () => {
  // React Router logs the missing-HydrateFallback warning only once per module (a module-level
  // warningOnce cache that vi.resetModules cannot clear), so a single dedicated test would only
  // catch it if it happened to do the file's first routed render. Guarding every test instead
  // fails whichever test renders first, in any order.
  let warn: MockInstance;
  beforeEach(() => {
    warn = vi.spyOn(console, 'warn');
  });
  afterEach(() => {
    expect(warn).not.toHaveBeenCalledWith(expect.stringContaining('HydrateFallback'));
  });

  it('builds a browser router over the same route tree', () => {
    const router = createAppRouter();

    expect(router.routes[0]?.children).toHaveLength(appRoutes[0]?.children?.length ?? -1);
    router.dispose();
  });

  it('renders the Sunday Sheet at /', async () => {
    renderRoute('/');

    expect(
      await screen.findByRole('heading', { level: 1, name: 'The Sunday Sheet' }, LAZY_CHART),
    ).toBeInTheDocument();
  });
});
