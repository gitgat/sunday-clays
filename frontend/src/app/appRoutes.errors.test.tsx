import { screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { renderRoutes } from '../test/render';
import { stubViewport } from '../test/viewport';
import { appRoutes } from './router';

// A registry with one page that always throws, standing in for any feature page that crashes.
// vi.mock is hoisted above the JSX runtime import, so the factory builds elements with createElement.
vi.mock('./registry', async () => {
  const { createElement } = await import('react');
  const { House } = await import('lucide-react');
  function Boom(): never {
    throw new Error('boom');
  }
  return {
    featureRoutes: [
      { index: true, element: createElement('p', null, 'home page') },
      { path: 'boom', element: createElement(Boom) },
    ],
    navItems: [{ label: 'Home', path: '/', icon: House, order: 10, mobileTab: true }],
  };
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('appRoutes page errors', () => {
  it('shows a crashed page inside the shell, so the navigation stays usable', async () => {
    stubViewport('desktop');
    // React and React Router both log the caught render error; keep the test output clean.
    const logged = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const { user } = renderRoutes(appRoutes, { route: '/boom' });

    const main = await screen.findByRole('main');
    expect(within(main).getByRole('heading', { name: 'Something went wrong' })).toBeInTheDocument();
    expect(logged).toHaveBeenCalled();

    await user.click(
      within(screen.getByRole('navigation', { name: 'Main' })).getByRole('link', { name: 'Home' }),
    );
    expect(screen.getByRole('main')).toHaveTextContent('home page');
    expect(screen.queryByRole('heading', { name: 'Something went wrong' })).toBeNull();
  });
});
