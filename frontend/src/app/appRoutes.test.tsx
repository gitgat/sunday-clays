import { screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { renderRoutes } from '../test/render';
import { stubViewport } from '../test/viewport';
import { appRoutes } from './router';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('appRoutes', () => {
  it('renders feature pages inside the AppShell layout', async () => {
    stubViewport('desktop');
    renderRoutes(appRoutes, { route: '/' });
    expect(await screen.findByRole('navigation', { name: 'Main' })).toBeInTheDocument();
    // Pages never render their own <main>: the shell's <main id="main"> is the only one.
    expect(screen.getByRole('main')).toHaveAttribute('id', 'main');
  });

  it('sends a signed-out visitor from / to the login page, outside the shell', async () => {
    const { router } = renderRoutes(appRoutes, { route: '/', role: null });
    expect(await screen.findByLabelText('Password')).toBeInTheDocument();
    expect(router.state.location.pathname + router.state.location.search).toBe('/login?next=%2F');
    expect(screen.queryByRole('navigation', { name: 'Main' })).toBeNull();
  });

  it('shows Page not found for an unknown path', async () => {
    renderRoutes(appRoutes, { route: '/no-such-page' });
    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
  });
});
