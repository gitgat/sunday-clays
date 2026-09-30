import type * as ReactRouter from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { renderRoutes } from '../../../test/render';
import { LoginPage } from './LoginPage';

// A data router's navigate() returns a promise; this one rejects, as React Router's does for a
// navigation it refuses. A plain function, not vi.fn(): a spy attaches its own handlers to the
// promises it returns, which would mark the rejection handled. vi.mock is hoisted, so both are
// created with vi.hoisted.
const { calls, navigate } = vi.hoisted(() => {
  const calls: unknown[][] = [];
  return {
    calls,
    navigate: (...args: unknown[]) => {
      calls.push(args);
      return Promise.reject(new Error('navigation refused'));
    },
  };
});

vi.mock('react-router', async (importOriginal) => ({
  ...(await importOriginal<typeof ReactRouter>()),
  useNavigate: () => navigate,
}));

const unhandled = vi.fn();

afterEach(() => {
  process.off('unhandledRejection', unhandled);
});

describe('LoginPage navigation', () => {
  it('never leaves an unhandled rejection when leaving the page fails', async () => {
    process.on('unhandledRejection', unhandled);
    renderRoutes([{ path: '/login', element: <LoginPage /> }], {
      route: '/login?next=%2Fclub',
      role: 'viewer',
    });
    await vi.waitFor(() => {
      expect(calls).toContainEqual(['/club', { replace: true }]);
    });
    // Node reports an unhandled rejection after the microtask queue drains.
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(unhandled).not.toHaveBeenCalled();
  });
});
