import { screen, within } from '@testing-library/react';
import { delay, http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { clearMe, setMe } from '../../../lib/me';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { insightFixture } from '../../insights/mocks';
import { newerText } from '../components/Masthead';
import { sheetExplainers } from '../explainers';
import { onThisDayPost, postFixture, sheetFixture, trophyPost } from '../mocks';
import { SheetPage } from './SheetPage';

afterEach(() => {
  clearMe();
  localStorage.clear();
  vi.restoreAllMocks();
});

function renderAt(route = '/sheet/2026-09-27') {
  return renderWithProviders(<SheetPage />, { route, path: '/sheet/:date' });
}

describe('SheetPage', () => {
  it('holds the page with one loading status, then shows the issue', async () => {
    server.use(
      http.get('*/api/sheet/:date', async () => {
        await delay(50);
        return HttpResponse.json(sheetFixture());
      }),
    );
    renderAt();
    expect(screen.getAllByRole('status')).toHaveLength(1);
    expect(screen.getByRole('status', { name: 'Loading the Sunday Sheet' })).toBeInTheDocument();
    expect(
      await screen.findByRole('heading', { level: 1, name: 'The Sunday Sheet' }),
    ).toBeInTheDocument();
    expect(screen.queryByRole('status', { name: 'Loading the Sunday Sheet' })).toBeNull();
  });

  it('shows the masthead, the four numbers, the feed in order and More closed', async () => {
    renderAt();
    expect(await screen.findByText('Sep 27, 2026 · Issue 310')).toBeInTheDocument();
    const numbers = screen.getByRole('region', { name: 'This Sunday in numbers' });
    for (const [label, value] of [
      ['Shooters', '23'],
      ['Field median', '39'],
      ['Top score', '49'],
      ['Trophies', '13'],
    ] as const) {
      expect(within(numbers).getByText(label)).toBeInTheDocument();
      expect(within(numbers).getByText(value)).toBeInTheDocument();
    }
    const posts = within(screen.getByRole('list', { name: 'Posts' })).getAllByRole('listitem');
    expect(posts.map((p) => p.dataset['postType'])).toEqual(['milestone', 'trophy', 'on_this_day']);
    expect(posts[0]).toHaveTextContent('New personal best for Ike Hadley: 46.');
    expect(screen.getByText('All round types · not affected by the filters')).toBeInTheDocument();
    expect(within(posts[1] as HTMLElement).getByRole('link', { name: 'Amy Ace' })).toHaveAttribute(
      'href',
      '/shooters/1',
    );
    const more = screen.getByText('More from this Sunday (1)').closest('details');
    expect(more).not.toHaveAttribute('open');
    expect(
      within(more as HTMLElement).getByRole('region', { name: 'Streaks' }),
    ).toBeInTheDocument();
  });

  it('links the previous issue and all issues, and the latest has no next', async () => {
    renderAt();
    const nav = await screen.findByRole('navigation', { name: 'Issues' });
    expect(within(nav).getByRole('link', { name: '← Previous issue' })).toHaveAttribute(
      'href',
      '/sheet/2026-09-13',
    );
    expect(within(nav).getByRole('link', { name: 'All issues' })).toHaveAttribute(
      'href',
      '/events',
    );
    expect(within(nav).queryByRole('link', { name: 'Next issue →' })).toBeNull();
  });

  it('asks for the latest issue when the URL names no date', async () => {
    const asked: string[] = [];
    server.use(
      http.get('*/api/sheet/latest', () => {
        asked.push('latest');
        return HttpResponse.json(sheetFixture());
      }),
    );
    renderWithProviders(<SheetPage />, { route: '/', path: '/' });
    expect(await screen.findByText('Sep 27, 2026 · Issue 310')).toBeInTheDocument();
    expect(asked).toEqual(['latest']);
  });

  it('asks for the issue of the date in the URL, and a past issue links the next one', async () => {
    const asked: string[] = [];
    server.use(
      http.get('*/api/sheet/:date', ({ params }) => {
        asked.push(String(params['date']));
        return HttpResponse.json(
          sheetFixture({
            masthead: {
              date: '2026-09-13',
              issue: 309,
              previous: null,
              next: '2026-09-27',
              latest: false,
              newer: null,
            },
          }),
        );
      }),
    );
    renderAt('/sheet/2026-09-13');
    const nav = await screen.findByRole('navigation', { name: 'Issues' });
    expect(asked).toEqual(['2026-09-13']);
    expect(within(nav).getByRole('link', { name: 'Next issue →' })).toHaveAttribute(
      'href',
      '/sheet/2026-09-27',
    );
    expect(within(nav).queryByRole('link', { name: '← Previous issue' })).toBeNull();
  });

  it('says there is no Sheet for a date without one, and links the way back', async () => {
    server.use(
      http.get('*/api/sheet/:date', () =>
        HttpResponse.json(
          { error: { code: 'sheet_not_found', message: 'No Sunday Sheet' } },
          { status: 404 },
        ),
      ),
    );
    renderAt('/sheet/2026-09-26');
    expect(await screen.findByText('No Sunday Sheet for this date')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Latest issue' })).toHaveAttribute('href', '/');
  });

  it('says so when the issue fails to load', async () => {
    server.use(
      http.get('*/api/sheet/:date', () =>
        HttpResponse.json({ error: { code: 'internal', message: 'Boom' } }, { status: 500 }),
      ),
    );
    renderAt();
    expect(await screen.findByText("Couldn't load the Sunday Sheet")).toBeInTheDocument();
    expect(screen.getByText('Try again in a moment.')).toBeInTheDocument();
    expect(screen.queryByText('Boom')).toBeNull();
  });

  it('says so when a Sunday has no posts yet', async () => {
    server.use(
      http.get('*/api/sheet/:date', () => HttpResponse.json(sheetFixture({ posts: [], more: [] }))),
    );
    renderAt();
    expect(await screen.findByText('Nothing to report for this Sunday yet')).toBeInTheDocument();
    expect(screen.queryByText(/More from this Sunday/)).toBeNull();
  });

  it('shows the counts but turns bumps off when this browser cannot remember a device', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => undefined);
    renderAt();
    expect(await screen.findByText('Bumps need this browser to remember you')).toBeInTheDocument();
    const button = await screen.findByRole('button', { name: 'Fist bump, 5 bumps' });
    expect(button).toBeDisabled();
  });

  it('sends this device’s id with the bump counts', async () => {
    const asked: (string | null)[] = [];
    server.use(
      http.get('*/api/sheet/:date/bumps', ({ request }) => {
        asked.push(new URL(request.url).searchParams.get('device_id'));
        return HttpResponse.json({});
      }),
    );
    renderAt();
    await screen.findByRole('heading', { level: 1, name: 'The Sunday Sheet' });
    await vi.waitFor(() => expect(asked).toHaveLength(1));
    expect(asked[0]).toBe(localStorage.getItem('sc.device'));
  });

  it('reads the viewer’s own insight post in the second person', async () => {
    setMe(3);
    renderAt();
    const posts = await screen.findByRole('list', { name: 'Posts' });
    expect(within(posts).getAllByRole('listitem')[0]).toHaveTextContent('New personal best: 46.');
  });

  it('notes a newer Sunday without full results and links it', async () => {
    server.use(
      http.get('*/api/sheet/:date', () =>
        HttpResponse.json(
          sheetFixture({
            masthead: {
              ...sheetFixture().masthead,
              newer: { date: '2026-10-04', has_scores: false, head_count: 14, n_shooters: 0 },
            },
          }),
        ),
      ),
    );
    renderAt();
    expect(
      await screen.findByText(
        'Newer Sunday, Oct 4, 2026: Attendance only — 14 shooters, no scores recorded.',
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'See Oct 4, 2026' })).toHaveAttribute(
      'href',
      '/events/2026-10-04',
    );
    const partial = { date: '2026-10-04', has_scores: true, head_count: null, n_shooters: 6 };
    expect(newerText(partial)).toBe('Partial results — 6 shooters so far');
    expect(newerText({ ...partial, has_scores: false })).toBe('No scores recorded');
  });

  it('lists everyone who earned a trophy: eight at first, the rest in place', async () => {
    const holders = Array.from({ length: 10 }, (_, i) => ({
      shooter_id: 100 + i,
      name: `Amy Ace${String(i + 1)}`,
    }));
    server.use(
      http.get('*/api/sheet/:date', () =>
        HttpResponse.json(
          sheetFixture({
            posts: [
              {
                ...trophyPost,
                trophy: {
                  code: 'first_win',
                  title: 'First win',
                  art_key: 'first_win',
                  metal: null,
                  holders,
                },
              },
            ],
          }),
        ),
      ),
    );
    const { user } = renderAt();
    const list = await screen.findByRole('list', { name: 'Earned by' });
    const links = within(list).getAllByRole('link', { hidden: true });
    expect(links.map((a) => a.getAttribute('href'))).toEqual(
      holders.map((h) => `/shooters/${String(h.shooter_id)}`),
    );
    expect(within(list).getAllByRole('link')).toHaveLength(8);
    await user.click(screen.getByRole('button', { name: '+2 more' }));
    expect(within(list).getAllByRole('link')).toHaveLength(10);
    expect(screen.getByRole('button', { name: 'Show fewer' })).toHaveAttribute(
      'aria-expanded',
      'true',
    );
  });

  it('keeps the insight card’s New tag, extra charts and "How we worked it out"', async () => {
    const insight = insightFixture({ is_new: true });
    const also = { ...insight.chart, label: 'Turnout per Sunday', label_you: null, also: [] };
    server.use(
      http.get('*/api/sheet/:date', () =>
        HttpResponse.json(
          sheetFixture({
            posts: [
              postFixture({ insight: { ...insight, chart: { ...insight.chart, also: [also] } } }),
              onThisDayPost,
            ],
          }),
        ),
      ),
    );
    const { user } = renderAt();
    const [post, otd] = within(await screen.findByRole('list', { name: 'Posts' })).getAllByRole(
      'listitem',
    ) as [HTMLElement, HTMLElement];
    expect(within(post).getByText('New')).toBeInTheDocument();
    expect(
      within(post).getByRole('link', { name: 'See the chart: Turnout per Sunday' }),
    ).toBeInTheDocument();
    await user.click(within(post).getByRole('button', { name: 'How we worked it out' }));
    expect(within(post).getByText('The best round beats every earlier round.')).toBeInTheDocument();
    await user.click(within(otd).getByRole('button', { name: 'How we worked it out' }));
    expect(within(otd).getByText(sheetExplainers.onThisDay.what)).toBeInTheDocument();
  });

  it('says so when the bump counts cannot be loaded, instead of showing silent zeros', async () => {
    server.use(
      http.get('*/api/sheet/:date/bumps', () =>
        HttpResponse.json({ error: { code: 'internal', message: 'Boom' } }, { status: 500 }),
      ),
    );
    renderAt();
    expect(await screen.findByText("Bump counts aren't available right now")).toBeInTheDocument();
  });

  it('reads an extra chart link in the second person for the viewer’s own insight', async () => {
    setMe(3);
    const insight = insightFixture();
    const also = {
      ...insight.chart,
      label: 'Hadley turnout',
      label_you: 'Your turnout',
      also: [],
    };
    server.use(
      http.get('*/api/sheet/:date', () =>
        HttpResponse.json(
          sheetFixture({
            posts: [
              postFixture({ insight: { ...insight, chart: { ...insight.chart, also: [also] } } }),
            ],
          }),
        ),
      ),
    );
    renderAt();
    expect(
      await screen.findByRole('link', { name: 'See the chart: Your turnout' }),
    ).toBeInTheDocument();
  });
});
