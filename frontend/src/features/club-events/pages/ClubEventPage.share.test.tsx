import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { server } from '../../../test/msw/server';
import { fallFunShoot } from '../mocks';
import { renderWithProviders } from '../../../test/render';
import { ClubEventPage } from './ClubEventPage';

const share = vi.hoisted(() => vi.fn());
vi.mock('../../../lib/share', () => ({ shareElementAsImage: share }));

afterEach(() => {
  vi.restoreAllMocks();
});

function renderPage() {
  return renderWithProviders(<ClubEventPage />, {
    route: '/club-events/1',
    path: '/club-events/:id',
  });
}

describe('ClubEventPage share, copy link and errors', () => {
  it('shares the page as an image', async () => {
    const { user } = renderPage();
    await user.click(await screen.findByRole('button', { name: 'Share' }));
    expect(share).toHaveBeenCalledWith(expect.any(HTMLElement), 'club-event-1');
  });

  it('copies the link and says so', async () => {
    const { user } = renderPage();
    await screen.findByRole('button', { name: 'Copy link' });
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.spyOn(navigator, 'clipboard', 'get').mockReturnValue({ writeText } as unknown as Clipboard);
    await user.click(screen.getByRole('button', { name: 'Copy link' }));
    expect(await screen.findByText('Link copied')).toBeInTheDocument();
    expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/club-events/1`);
  });

  it('shows the link itself when copying is blocked', async () => {
    const { user } = renderPage();
    await screen.findByRole('button', { name: 'Copy link' });
    const writeText = vi.fn().mockRejectedValue(new Error('blocked'));
    vi.spyOn(navigator, 'clipboard', 'get').mockReturnValue({ writeText } as unknown as Clipboard);
    await user.click(screen.getByRole('button', { name: 'Copy link' }));
    expect(await screen.findByText(`${window.location.origin}/club-events/1`)).toBeInTheDocument();
  });

  it('shows the not-on-the-list page for a bad id and for a 404', async () => {
    const first = renderWithProviders(<ClubEventPage />, {
      route: '/club-events/abc',
      path: '/club-events/:id',
    });
    expect(await screen.findByText("That club event isn't on the list.")).toBeInTheDocument();
    first.unmount();
    server.use(http.get('*/api/club-events/:id', () => HttpResponse.json({}, { status: 404 })));
    renderPage();
    expect(await screen.findByText("That club event isn't on the list.")).toBeInTheDocument();
  });

  it('says it could not load, with a retry, on any other error', async () => {
    let calls = 0;
    server.use(
      http.get('*/api/club-events/:id', () => {
        calls += 1;
        return calls === 1
          ? HttpResponse.json({}, { status: 500 })
          : HttpResponse.json(fallFunShoot);
      }),
    );
    const { user } = renderPage();
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Could not load this club event. Try again.',
    );
    expect(screen.queryByText("That club event isn't on the list.")).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Try again' }));
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Fall Fun Shoot' }),
    ).toBeInTheDocument();
  });
});
