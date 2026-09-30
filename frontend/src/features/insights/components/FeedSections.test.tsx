import { screen, waitFor, within } from '@testing-library/react';
import { delay, http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it } from 'vitest';
import { clearMe, setMe } from '../../../lib/me';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { feedFixture, insightFixture, kudosFixture } from '../mocks';
import { HomeInsights, PageInsights, ProfileInsights, SundayInsights } from './FeedSections';

afterEach(() => {
  clearMe();
});

const digest = insightFixture({
  key: 'digest',
  kind: 'pf.digest-line',
  family: 'recap',
  headline: [
    { t: 'text', v: 'Sunday 9/27: ' },
    { t: 'shooter', v: 'Ike Hadley', id: 3 },
    { t: 'text', v: ' shot 44.' },
  ],
  headline_you: [{ t: 'text', v: 'Sunday 9/27: you shot 44.' }],
});

function profileFeed() {
  server.use(
    http.get('*/api/insights/shooters/:id', () =>
      HttpResponse.json(feedFixture({ pinned: digest, top: [insightFixture()] })),
    ),
  );
}

describe('ProfileInsights', () => {
  it('shows any viewer the digest line and insights in the third person', async () => {
    profileFeed();
    setMe(9);
    renderWithProviders(<ProfileInsights shooterId={3} />);
    const card = await screen.findByRole('region', { name: 'Insights' });
    expect(within(card).getByText(/shot 44\./)).toBeInTheDocument();
    expect(within(card).getAllByRole('link', { name: 'Ike Hadley' })).toHaveLength(2);
    expect(within(card).getByText(/New personal best for/)).toBeInTheDocument();
  });

  it('says what date it is as of, and "Show all N" asks the server for the whole list', async () => {
    const requests: URLSearchParams[] = [];
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.get('*/api/insights/shooters/:id', async ({ request }) => {
        const params = new URL(request.url).searchParams;
        requests.push(params);
        if (params.has('all')) await gate;
        const more = [insightFixture({ key: 'm1', family: 'streak' })];
        return HttpResponse.json(
          feedFixture({
            top: [insightFixture()],
            more: params.has('all')
              ? [...more, insightFixture({ key: 'm2', family: 'streak' })]
              : more,
            n_more: 2,
          }),
        );
      }),
    );
    const { user } = renderWithProviders(<ProfileInsights shooterId={3} />);
    const card = await screen.findByRole('region', { name: 'Insights' });
    expect(
      within(card).getByText('As of Sep 27, 2026 · not affected by the time filter'),
    ).toBeVisible();
    await user.click(within(card).getByText('More insights (2)'));
    await user.click(within(card).getByRole('button', { name: 'Show all 2' }));
    expect(within(card).getByRole('button', { name: 'Loading…' })).toBeDisabled();
    release();
    await waitFor(() => expect(within(card).getAllByRole('listitem').length).toBeGreaterThan(2));
    expect(requests.at(-1)?.get('all')).toBe('true');
    expect(within(card).queryByRole('button', { name: /Show all/ })).toBeNull();
  });

  it('reads in the second person for "That\'s me"', async () => {
    profileFeed();
    setMe(3);
    renderWithProviders(<ProfileInsights shooterId={3} />);
    const card = await screen.findByRole('region', { name: 'Insights' });
    expect(within(card).getByText('Sunday 9/27: you shot 44.')).toBeInTheDocument();
  });

  it('stays silent when nothing passes', async () => {
    let hits = 0;
    server.use(
      http.get('*/api/insights/shooters/:id', () => {
        hits += 1;
        return HttpResponse.json(feedFixture());
      }),
    );
    const { container } = renderWithProviders(<ProfileInsights shooterId={3} />);
    await waitFor(() => {
      expect(hits).toBe(1);
    });
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when the feed request fails', async () => {
    let hits = 0;
    server.use(
      http.get('*/api/insights/shooters/:id', () => {
        hits += 1;
        return HttpResponse.json({ detail: 'boom' }, { status: 500 });
      }),
    );
    const { container } = renderWithProviders(<ProfileInsights shooterId={3} />);
    await waitFor(() => {
      expect(hits).toBeGreaterThanOrEqual(1);
    });
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(container).toBeEmptyDOMElement();
  });
});

describe('SundayInsights', () => {
  it("reads the viewer's own cards in the second person, four to a row on desktop", async () => {
    server.use(
      http.get('*/api/insights/sundays/:date', () =>
        HttpResponse.json(feedFixture({ top: [insightFixture()] })),
      ),
    );
    setMe(3);
    renderWithProviders(<SundayInsights date="2026-09-27" />);
    const list = await screen.findByRole('list', { name: 'Top insights' });
    expect(within(list).getByText(/New personal best:/)).toBeInTheDocument();
    expect(list).toHaveClass('lg:grid-cols-4');
    expect(screen.getByText('Sep 27, 2026 · not affected by the time filter')).toBeInTheDocument();
  });

  it('shows the conditions card first, then the top insights and kudos', async () => {
    const conditions = insightFixture({
      key: 'rain',
      kind: 'ev.rain-day',
      headline: [{ t: 'text', v: 'Rain Sunday.' }],
      headline_you: null,
    });
    server.use(
      http.get('*/api/insights/sundays/:date', () =>
        HttpResponse.json(
          feedFixture({ conditions, top: [insightFixture()], kudos: kudosFixture(2) }),
        ),
      ),
    );
    renderWithProviders(<SundayInsights date="2026-09-27" />);
    const list = await screen.findByRole('list', { name: 'Top insights' });
    const items = within(list).getAllByRole('listitem');
    expect(items[0]).toHaveTextContent('Rain Sunday.');
    expect(screen.getByRole('region', { name: 'Kudos' })).toBeInTheDocument();
  });
});

describe('HomeInsights', () => {
  it('holds the place of the cards while the feed loads, then swaps them for the real ones', async () => {
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.get('*/api/insights/home', async () => {
        await gate;
        return HttpResponse.json(
          feedFixture({
            pinned: insightFixture({ key: 'recap', kind: 'home.sunday-recap' }),
            hero: insightFixture({ key: 'hero' }),
            top: [insightFixture({ key: 'top' })],
          }),
        );
      }),
    );
    const { container } = renderWithProviders(<HomeInsights meId={3} />);
    expect(screen.getByRole('status', { name: 'Loading insights' })).toBeInTheDocument();
    // Two cards side by side on desktop, then the Insights card: three placeholders in all.
    expect(container.querySelector('.lg\\:grid-cols-2')?.children).toHaveLength(2);
    expect(container.querySelectorAll('[data-skeleton-line]').length).toBeGreaterThan(8);
    expect(screen.queryByRole('region', { name: 'Last Sunday' })).not.toBeInTheDocument();
    release();
    expect(await screen.findByRole('region', { name: 'Last Sunday' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Top story' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Insights' })).toBeInTheDocument();
    expect(screen.queryByRole('status', { name: 'Loading insights' })).not.toBeInTheDocument();
    expect(container.querySelector('[data-skeleton-line]')).toBeNull();
  });

  it('keeps the placeholder up while the request is still pending', async () => {
    server.use(http.get('*/api/insights/home', () => delay('infinite')));
    renderWithProviders(<HomeInsights meId={null} />);
    expect(screen.getByRole('status', { name: 'Loading insights' })).toBeInTheDocument();
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.getByRole('status', { name: 'Loading insights' })).toBeInTheDocument();
  });

  it('shows nothing once the feed has loaded empty, and nothing on a fetch error', async () => {
    server.use(http.get('*/api/insights/home', () => HttpResponse.json(feedFixture())));
    const empty = renderWithProviders(<HomeInsights meId={null} />);
    await waitFor(() =>
      expect(screen.queryByRole('status', { name: 'Loading insights' })).not.toBeInTheDocument(),
    );
    expect(empty.container).toBeEmptyDOMElement();
    empty.unmount();
    server.use(http.get('*/api/insights/home', () => new HttpResponse(null, { status: 500 })));
    const failed = renderWithProviders(<HomeInsights meId={null} />);
    await waitFor(() =>
      expect(screen.queryByRole('status', { name: 'Loading insights' })).not.toBeInTheDocument(),
    );
    expect(failed.container).toBeEmptyDOMElement();
  });

  it("shows the latest Sunday's kudos, with the recap and the top story side by side, each dated", async () => {
    server.use(
      http.get('*/api/insights/home', () =>
        HttpResponse.json(
          feedFixture({
            pinned: insightFixture({ key: 'recap', kind: 'home.sunday-recap' }),
            hero: insightFixture({ key: 'hero' }),
            kudos: kudosFixture(2),
          }),
        ),
      ),
    );
    renderWithProviders(<HomeInsights meId={3} />);
    const hero = await screen.findByRole('list', { name: 'Top story' });
    expect(within(hero).getByText(/New personal best:/)).toBeInTheDocument();
    expect(hero.closest('.lg\\:grid-cols-2')).not.toBeNull();
    expect(screen.getByRole('region', { name: 'Kudos from Sep 27' })).toBeInTheDocument();
    // The latest-Sunday cards name their Sunday and say the time filter does not move them.
    for (const card of ['Last Sunday', 'Top story']) {
      expect(screen.getByRole('region', { name: card })).toHaveTextContent(
        'Sep 27, 2026 · not affected by the time filter',
      );
    }
  });

  it('still labels the latest-Sunday cards when the feed carries no date', async () => {
    server.use(
      http.get('*/api/insights/home', () =>
        HttpResponse.json(
          feedFixture({
            as_of: null,
            pinned: insightFixture({ key: 'recap', kind: 'home.sunday-recap', anchor_date: null }),
            hero: insightFixture({ key: 'hero', anchor_date: null }),
            spotlight: insightFixture({ key: 'spot' }),
            kudos: kudosFixture(2),
          }),
        ),
      ),
    );
    renderWithProviders(<HomeInsights meId={3} />);
    expect(await screen.findByRole('region', { name: 'Last Sunday' })).toHaveTextContent(
      'Not affected by the time filter',
    );
    expect(screen.getByRole('region', { name: 'Top story' })).toHaveTextContent(
      'Not affected by the time filter',
    );
    expect(screen.getByRole('region', { name: 'Kudos' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Insights' })).toHaveTextContent(
      'Not affected by the time filter',
    );
  });

  it('pins the recap and shows the hero, the shooter to know and the rest', async () => {
    const recap = insightFixture({
      key: 'recap',
      kind: 'home.sunday-recap',
      headline: [{ t: 'text', v: 'Sunday 9/27: 23 shooters.' }],
    });
    server.use(
      http.get('*/api/insights/home', () =>
        HttpResponse.json(
          feedFixture({
            pinned: recap,
            hero: insightFixture({ key: 'hero' }),
            spotlight: insightFixture({ key: 'spot' }),
            top: [insightFixture({ key: 'top' })],
          }),
        ),
      ),
    );
    renderWithProviders(<HomeInsights meId={null} />);
    expect(await screen.findByRole('region', { name: 'Last Sunday' })).toHaveTextContent(
      'Sunday 9/27: 23 shooters.',
    );
    expect(screen.getByRole('list', { name: 'Top story' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Shooter to know' })).toBeInTheDocument();
    expect(screen.getByRole('list', { name: 'Around the club' })).toBeInTheDocument();
  });
});

describe('PageInsights', () => {
  it.each(['club', 'leaderboards', 'records', 'stations'] as const)(
    'shows the %s feed: top insights and the rest',
    async (page) => {
      server.use(
        http.get(`*/api/insights/${page}`, () =>
          HttpResponse.json(
            feedFixture({
              top: [insightFixture({ key: `${page}-top` })],
              more: [insightFixture({ key: `${page}-more` })],
              n_more: 1,
            }),
          ),
        ),
      );
      renderWithProviders(<PageInsights page={page} />);
      const card = await screen.findByRole('region', { name: 'Insights' });
      expect(within(card).getByRole('list', { name: 'Top insights' })).toBeInTheDocument();
      expect(
        within(card).getByText(/^As of .* · not affected by the time filter$/),
      ).toBeInTheDocument();
    },
  );

  it('ignores a stale as_of under a custom window', async () => {
    const seasons: (string | null)[] = [];
    server.use(
      http.get('*/api/insights/leaderboards', ({ request }) => {
        seasons.push(new URL(request.url).searchParams.get('season'));
        return HttpResponse.json(feedFixture({ top: [insightFixture()] }));
      }),
    );
    renderWithProviders(<PageInsights page="leaderboards" />, {
      route: '/leaderboards?as_of=2025-06-01&w=2026-01-01..2026-02-01',
    });
    await screen.findByRole('region', { name: 'Insights' });
    expect(seasons).toEqual([null]);
  });

  it('asks the leaderboards feed for the season the time machine shows', async () => {
    const seasons: (string | null)[] = [];
    server.use(
      http.get('*/api/insights/leaderboards', ({ request }) => {
        seasons.push(new URL(request.url).searchParams.get('season'));
        return HttpResponse.json(feedFixture({ top: [insightFixture()] }));
      }),
    );
    renderWithProviders(<PageInsights page="leaderboards" />, {
      route: '/leaderboards?as_of=2025-06-01',
    });
    await screen.findByRole('region', { name: 'Insights' });
    expect(seasons).toEqual(['2025']);
  });

  it('stays silent when the page has no insights', async () => {
    let served = false;
    server.use(
      http.get('*/api/insights/records', () => {
        served = true;
        return HttpResponse.json(feedFixture());
      }),
    );
    const { queryClient } = renderWithProviders(<PageInsights page="records" />);
    await waitFor(() => expect(served).toBe(true));
    await waitFor(() => expect(queryClient.isFetching()).toBe(0));
    expect(screen.queryByRole('region', { name: 'Insights' })).toBeNull();
  });
});
