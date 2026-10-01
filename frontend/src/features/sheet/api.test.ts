import { describe, expect, it } from 'vitest';
import { toggled } from './api';

describe('toggled', () => {
  it('adds and takes back this device’s bump', () => {
    const start = { k: { bumps: 2, bumped: false } };
    expect(toggled(start, 'k', true)).toEqual({ k: { bumps: 3, bumped: true } });
    expect(toggled({ k: { bumps: 3, bumped: true } }, 'k', false)).toEqual({
      k: { bumps: 2, bumped: false },
    });
  });

  it('is a no-op when the state already matches, and never goes below zero', () => {
    expect(toggled({ k: { bumps: 3, bumped: true } }, 'k', true)).toEqual({
      k: { bumps: 3, bumped: true },
    });
    expect(toggled({ k: { bumps: 0, bumped: true } }, 'k', false)).toEqual({
      k: { bumps: 0, bumped: false },
    });
  });

  it('starts a post nobody bumped at zero and keeps the other posts', () => {
    expect(toggled(undefined, 'k', true)).toEqual({ k: { bumps: 1, bumped: true } });
    expect(toggled({ j: { bumps: 4, bumped: false } }, 'k', true)).toEqual({
      j: { bumps: 4, bumped: false },
      k: { bumps: 1, bumped: true },
    });
  });
});
