import { describe, expect, it } from 'vitest';
import { ApiError } from '../api/errors';
import { createQueryClient, shouldRetry } from './queryClient';

describe('shouldRetry', () => {
  it('never retries a 4xx answer', () => {
    expect(shouldRetry(0, new ApiError(404, 'not_found', 'x'))).toBe(false);
    expect(shouldRetry(0, new ApiError(401, 'http_401', 'x'))).toBe(false);
  });

  it('retries 5xx and network errors twice', () => {
    const e500 = new ApiError(503, 'http_503', 'x');
    expect([0, 1, 2].map((n) => shouldRetry(n, e500))).toEqual([true, true, false]);
    expect([0, 1, 2].map((n) => shouldRetry(n, new TypeError('fetch failed')))).toEqual([
      true,
      true,
      false,
    ]);
  });
});

describe('createQueryClient', () => {
  it('uses the retry policy and does not refetch on window focus', () => {
    const defaults = createQueryClient().getDefaultOptions();
    expect(defaults.queries?.retry).toBe(shouldRetry);
    expect(defaults.queries?.refetchOnWindowFocus).toBe(false);
    expect(defaults.mutations?.retry).toBe(false);
  });
});
