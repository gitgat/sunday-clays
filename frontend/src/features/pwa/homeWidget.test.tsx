import { act, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { resetInstallPromptForTests } from '../../lib/installPrompt';
import { markTourDone, resetTourForTests, TOUR_KEY } from '../tour/state';
import { server } from '../../test/msw/server';
import { renderWithProviders } from '../../test/render';
import { homeWidget, LAUNCHED_KEY } from './homeWidget';

const { Component } = homeWidget;

function media(matches: Record<string, boolean>) {
  vi.spyOn(window, 'matchMedia').mockImplementation(
    (query: string) =>
      ({
        matches: matches[query] ?? false,
        media: query,
        addEventListener: () => undefined,
        removeEventListener: () => undefined,
      }) as unknown as MediaQueryList,
  );
}

function fireInstallPrompt() {
  const event = Object.assign(new Event('beforeinstallprompt', { cancelable: true }), {
    prompt: vi.fn().mockResolvedValue(undefined),
    userChoice: Promise.resolve({ outcome: 'dismissed' as const }),
  });
  window.dispatchEvent(event);
  return event;
}

beforeEach(() => {
  server.use(http.get('*/api/features', () => HttpResponse.json({ switches: { pwa: true } })));
});
afterEach(() => {
  resetInstallPromptForTests();
  resetTourForTests();
  localStorage.removeItem(TOUR_KEY);
  sessionStorage.clear();
});

describe('install tip and launch redirect', () => {
  it('declares a main widget at order 90', () => {
    expect(homeWidget).toMatchObject({ id: 'install', order: 90, slot: 'main' });
  });

  it('shows the Android tip after the install event, and Not now hides it for good', async () => {
    media({ '(pointer: coarse)': true });
    const { user } = renderWithProviders(<Component meId={null} />);
    fireInstallPrompt();
    expect(
      await screen.findByRole('heading', { name: 'Add Sunday Clays to your home screen' }),
    ).toBeInTheDocument();
    expect(
      screen.getByText('Opens like an app, straight to Home or to your own page.'),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Not now' }));
    expect(localStorage.getItem('sc.install.dismissed')).toBe('1');
    expect(screen.queryByRole('heading', { name: /home screen/ })).not.toBeInTheDocument();
  });

  it('moves focus to the Home heading when the tip is dismissed', async () => {
    media({ '(pointer: coarse)': true });
    const { user } = renderWithProviders(
      <>
        <h1 id="home-title" tabIndex={-1}>
          Home
        </h1>
        <Component meId={null} />
      </>,
    );
    fireInstallPrompt();
    await user.click(await screen.findByRole('button', { name: 'Not now' }));
    expect(screen.getByRole('heading', { level: 1, name: 'Home' })).toHaveFocus();
  });

  it('moves focus to the Home heading after Got it on iPhone Safari', async () => {
    media({ '(pointer: coarse)': true });
    vi.spyOn(navigator, 'userAgent', 'get').mockReturnValue(
      'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    );
    const { user } = renderWithProviders(
      <>
        <h1 id="home-title" tabIndex={-1}>
          Home
        </h1>
        <Component meId={null} />
      </>,
    );
    await user.click(await screen.findByRole('button', { name: 'Got it' }));
    expect(screen.getByRole('heading', { level: 1, name: 'Home' })).toHaveFocus();
  });

  it('Install calls prompt()', async () => {
    media({ '(pointer: coarse)': true });
    const { user } = renderWithProviders(<Component meId={null} />);
    const event = fireInstallPrompt();
    await user.click(await screen.findByRole('button', { name: 'Install' }));
    expect(event.prompt).toHaveBeenCalled();
  });

  it('shows the iOS tip on iPhone Safari without any event', async () => {
    media({ '(pointer: coarse)': true });
    vi.spyOn(navigator, 'userAgent', 'get').mockReturnValue(
      'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    );
    renderWithProviders(<Component meId={null} />);
    expect(
      await screen.findByText('Tap the Share button, then “Add to Home Screen”.'),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Got it' })).toBeInTheDocument();
  });

  it.each([
    ['on a desktop', { '(pointer: coarse)': false }],
    ['when installed', { '(pointer: coarse)': true, '(display-mode: standalone)': true }],
  ])('stays hidden %s', async (_name, matches) => {
    media(matches);
    const { container } = renderWithProviders(<Component meId={null} />);
    fireInstallPrompt();
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(container).toBeEmptyDOMElement();
  });

  it('waits for the tour to be done', async () => {
    media({ '(pointer: coarse)': true });
    server.use(
      http.get('*/api/features', () =>
        HttpResponse.json({ switches: { pwa: true, tour_glossary: true } }),
      ),
    );
    const { container } = renderWithProviders(<Component meId={null} />);
    fireInstallPrompt();
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(container).toBeEmptyDOMElement();
    act(() => markTourDone());
    expect(
      await screen.findByRole('heading', { name: 'Add Sunday Clays to your home screen' }),
    ).toBeInTheDocument();
  });

  it('does not redirect an installed app while the pwa switch is off', async () => {
    media({ '(display-mode: standalone)': true });
    localStorage.setItem('sc.me', '3');
    server.use(http.get('*/api/features', () => HttpResponse.json({ switches: {} })));
    const { router } = renderWithProviders(<Component meId={3} />, { route: '/' });
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(router.state.location.pathname).toBe('/');
    expect(sessionStorage.getItem(LAUNCHED_KEY)).toBeNull();
  });

  it('opens an installed app on the viewer’s own page once per session', async () => {
    media({ '(display-mode: standalone)': true });
    localStorage.setItem('sc.me', '3');
    const { router } = renderWithProviders(<Component meId={3} />, { route: '/' });
    await waitFor(() => expect(router.state.location.pathname).toBe('/shooters/3'));
    expect(sessionStorage.getItem(LAUNCHED_KEY)).toBe('1');
  });

  it('decides once per page load: a name picked later does not bounce a Home tap', async () => {
    media({ '(display-mode: standalone)': true });
    const first = renderWithProviders(<Component meId={null} />, { route: '/' });
    await waitFor(() => expect(sessionStorage.getItem(LAUNCHED_KEY)).not.toBeNull());
    first.unmount();
    localStorage.setItem('sc.me', '3');
    const second = renderWithProviders(<Component meId={3} />, { route: '/' });
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(second.router.state.location.pathname).toBe('/');
  });

  it('stays on Home without a picked name, or once already launched', async () => {
    media({ '(display-mode: standalone)': true });
    const first = renderWithProviders(<Component meId={null} />, { route: '/' });
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(first.router.state.location.pathname).toBe('/');
    first.unmount();
    localStorage.setItem('sc.me', '3');
    sessionStorage.setItem(LAUNCHED_KEY, '1');
    const second = renderWithProviders(<Component meId={3} />, { route: '/' });
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(second.router.state.location.pathname).toBe('/');
  });
});
