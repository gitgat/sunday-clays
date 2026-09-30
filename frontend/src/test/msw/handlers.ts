import type { RequestHandler } from 'msw';

/** Merges every src/features/<name>/mocks.ts `handlers` export (C10). */
const featureMocks = import.meta.glob<{ handlers: RequestHandler[] }>('../../features/*/mocks.ts', {
  eager: true,
});

export const handlers: RequestHandler[] = Object.keys(featureMocks)
  .sort()
  .flatMap((key) => featureMocks[key]?.handlers ?? []);
