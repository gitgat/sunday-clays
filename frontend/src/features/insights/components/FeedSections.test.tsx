import { screen, waitFor, within } from '@testing-library/react';
import { delay, http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { clearMe, setMe } from '../../../lib/me';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { feedKeys } from '../feedKeys';
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

/** Records every GET /api/bumps and answers `counts` (zeros for any other asked key). */
function bumpCounts(counts: Record<string, { bumps: number; bumped: boolean }> = {}) {
  const asked: URLSearchParams[] = [];
  server.use(
    http.get('*/api/bumps', ({ request }) => {
      const params = new URL(request.url).searchParams;
      asked.push(params);
      const keys = (params.get('keys') ?? '').split(',').filter(Boolean);
      return HttpResponse.json(
        Object.fromEntries(keys.map((k) => [k, counts[k] ?? { bumps: 0, bumped: false }])),
      );
    }),
  );
  return asked;
}

const homeBumpFeed = feedFixture({
  pinned: insightFixture({ key: 'recap', kind: 'home.sunday-recap', family: 'recap' }),
  hero: insightFixture({ key: 'hero' }),
  spotlight: insightFixture({ key: 'spot' }),
  top: [insightFixture({ key: 't1' }), insightFixture({ key: 't2' })],
  kudos: kudosFixture(2),
  more: [insightFixture({ key: 'm1', family: 'streak' })],
  n_more: 1,
});

describe('fist bumps on every feed', () => {
  it('Home asks for every insight’s bumps in one request and puts a button on each row', async () => {
    server.use(http.get('*/api/insights/home', () => HttpResponse.json(homeBumpFeed)));
    const asked = bumpCounts({ hero: { bumps: 4, bumped: false } });
    const { container } = renderWithProviders(<HomeInsights meId={null} />);
    const topStory = await screen.findByRole('list', { name: 'Top story' });
    expect(
      await within(topStory).findByRole('button', { name: 'Fist bump, 4 bumps' }),
    ).toBeInTheDocument();
    expect(asked).toHaveLength(1);
    expect(asked[0]?.get('keys')).toBe([...new Set(feedKeys(homeBumpFeed))].sort().join(','));
    for (const key of ['recap', 'spot', 't1', 't2', 'm1']) {
      const row = container.querySelector(`[data-insight-key="${key}"]`);
      expect(row, key).not.toBeNull();
      const bump = within(row as HTMLElement).getByRole('button', { name: /^Fist bump/ });
      expect(bump).toHaveAccessibleDescription(/\S/);
    }
  });

  it.each([
    ['a profile', () => <ProfileInsights shooterId={3} />, '*/api/insights/shooters/:id'],
    ['a Sunday', () => <SundayInsights date="2026-09-27" />, '*/api/insights/sundays/:date'],
    ['the club page', () => <PageInsights page="club" />, '*/api/insights/club'],
  ])('%s puts a fist bump on its insights', async (_name, ui, route) => {
    server.use(http.get(route, () => HttpResponse.json(feedFixture({ top: [insightFixture()] }))));
    const asked = bumpCounts({ 'k-pb-3': { bumps: 2, bumped: true } });
    renderWithProviders(ui());
    const button = await screen.findByRole('button', { name: 'Fist bump, 2 bumps' });
    expect(button).toHaveAttribute('aria-pressed', 'true');
    expect(asked).toHaveLength(1);
  });

  it('one insight shown twice shares one count', async () => {
    const shared = insightFixture();
    server.use(
      http.get('*/api/insights/sundays/:date', () =>
        HttpResponse.json(
          feedFixture({
            top: [shared],
            kudos: [{ shooter_id: 3, display_name: 'Hadley, Ike', insight: shared }],
          }),
        ),
      ),
      http.post('*/api/bumps', () => HttpResponse.json({ bumps: 1, bumped: true })),
    );
    bumpCounts();
    const { user } = renderWithProviders(<SundayInsights date="2026-09-27" />);
    const top = await screen.findByRole('list', { name: 'Top insights' });
    await within(top).findByRole('button', { name: 'Fist bump, 0 bumps' });
    await user.click(screen.getByRole('button', { name: /Ike Hadley · / }));
    const sheet = await screen.findByRole('dialog');
    await user.click(within(sheet).getByRole('button', { name: 'Fist bump, 0 bumps' }));
    // The open Sheet makes the page behind it inert, so the list is queried with hidden: true.
    expect(
      await within(top).findByRole('button', { name: 'Fist bump, 1 bump', hidden: true }),
    ).toHaveAttribute('aria-pressed', 'true');
  });

  it('keeps the counts on screen while Show all loads more', async () => {
    let releaseSecond: () => void = () => undefined;
    const secondHeld = new Promise<void>((resolve) => {
      releaseSecond = resolve;
    });
    let gets = 0;
    server.use(
      http.get('*/api/insights/shooters/:id', ({ request }) => {
        const all = new URL(request.url).searchParams.has('all');
        const more = [insightFixture({ key: 'm1', family: 'streak' })];
        if (all) more.push(insightFixture({ key: 'm2', family: 'streak' }));
        return HttpResponse.json(feedFixture({ top: [insightFixture()], more, n_more: 2 }));
      }),
      http.get('*/api/bumps', async ({ request }) => {
        gets += 1;
        if (gets === 2) await secondHeld;
        const keys = (new URL(request.url).searchParams.get('keys') ?? '').split(',');
        return HttpResponse.json(
          Object.fromEntries(
            keys.map((k) => [k, { bumps: k === 'k-pb-3' ? 5 : 0, bumped: false }]),
          ),
        );
      }),
    );
    const { user } = renderWithProviders(<ProfileInsights shooterId={3} />);
    const top = await screen.findByRole('list', { name: 'Top insights' });
    await within(top).findByRole('button', { name: 'Fist bump, 5 bumps' });
    await user.click(screen.getByRole('button', { name: 'Show all 2' }));
    await waitFor(() => expect(gets).toBe(2));
    // The second ask is held: the card on screen keeps its 5, not a flash to 0.
    expect(within(top).getByRole('button', { name: 'Fist bump, 5 bumps' })).toBeInTheDocument();
    releaseSecond();
  });

  it('a tap while Show all loads keeps the other cards’ counts', async () => {
    let releaseSecond: () => void = () => undefined;
    const secondHeld = new Promise<void>((resolve) => {
      releaseSecond = resolve;
    });
    let releasePost: () => void = () => undefined;
    const postHeld = new Promise<void>((resolve) => {
      releasePost = resolve;
    });
    let gets = 0;
    const counts: Record<string, { bumps: number; bumped: boolean }> = {
      'k-pb-3': { bumps: 5, bumped: false },
      t2: { bumps: 2, bumped: false },
    };
    server.use(
      http.get('*/api/insights/shooters/:id', ({ request }) => {
        const all = new URL(request.url).searchParams.has('all');
        const more = [insightFixture({ key: 'm1', family: 'streak' })];
        if (all) more.push(insightFixture({ key: 'm2', family: 'streak' }));
        return HttpResponse.json(
          feedFixture({ top: [insightFixture(), insightFixture({ key: 't2' })], more, n_more: 2 }),
        );
      }),
      http.get('*/api/bumps', async ({ request }) => {
        gets += 1;
        if (gets === 2) await secondHeld;
        const keys = (new URL(request.url).searchParams.get('keys') ?? '').split(',');
        return HttpResponse.json(
          Object.fromEntries(keys.map((k) => [k, counts[k] ?? { bumps: 0, bumped: false }])),
        );
      }),
      http.post('*/api/bumps', async () => {
        await postHeld;
        counts.t2 = { bumps: 3, bumped: true };
        return HttpResponse.json(counts.t2);
      }),
    );
    const { user, container } = renderWithProviders(<ProfileInsights shooterId={3} />);
    const top = await screen.findByRole('list', { name: 'Top insights' });
    await within(top).findByRole('button', { name: 'Fist bump, 5 bumps' });
    const t2 = () => container.querySelector('[data-insight-key="t2"]') as HTMLElement;
    await within(t2()).findByRole('button', { name: 'Fist bump, 2 bumps' });
    await user.click(screen.getByRole('button', { name: 'Show all 2' }));
    await waitFor(() => expect(gets).toBe(2));
    // The new counts are still held. Tap a card already on screen.
    await user.click(within(t2()).getByRole('button', { name: 'Fist bump, 2 bumps' }));
    expect(await within(t2()).findByRole('button', { name: 'Fist bump, 3 bumps' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    // The other card keeps its 5: the tap is seeded from the counts on screen, not an empty map.
    // The POST is still held here, so nothing has refetched to paper over a bad seed.
    expect(within(top).getByRole('button', { name: 'Fist bump, 5 bumps' })).toBeInTheDocument();
    releasePost();
    releaseSecond();
    await waitFor(() =>
      expect(within(t2()).getByRole('button', { name: 'Fist bump, 3 bumps' })).toBeInTheDocument(),
    );
    expect(within(top).getByRole('button', { name: 'Fist bump, 5 bumps' })).toBeInTheDocument();
  });

  it('turns bumps off, says why once, and still shows counts when storage is blocked', async () => {
    server.use(http.get('*/api/insights/home', () => HttpResponse.json(homeBumpFeed)));
    const asked = bumpCounts({ hero: { bumps: 4, bumped: false } });
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError');
    });
    renderWithProviders(<HomeInsights meId={null} />);
    const button = await screen.findByRole('button', { name: 'Fist bump, 4 bumps' });
    expect(button).toBeDisabled();
    const notes = screen.getAllByText('Bumps need this browser to remember you');
    expect(notes).toHaveLength(1);
    // The note sits inside the Insights card, not as a bare line between widgets.
    expect(
      within(screen.getByRole('region', { name: 'Insights' })).getByText(
        notes[0]?.textContent ?? '',
      ),
    ).toBe(notes[0]);
    expect(button).toHaveAccessibleDescription(/remember you .+/);
    expect(asked[0]?.has('device_id')).toBe(false);
  });

  it.each([
    ['a lone top story', { hero: insightFixture({ key: 'hero' }) }, 'Top story'],
    ['a lone recap', { pinned: insightFixture({ key: 'recap' }) }, null],
  ])('says why bumps are off once for %s', async (_name, feedBits, card) => {
    server.use(http.get('*/api/insights/home', () => HttpResponse.json(feedFixture(feedBits))));
    bumpCounts();
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError');
    });
    renderWithProviders(<HomeInsights meId={null} />);
    await screen.findByRole('button', { name: /^Fist bump/ });
    const note = screen.getByText('Bumps need this browser to remember you');
    if (card !== null) {
      expect(
        within(screen.getByRole('region', { name: card })).getByText(note.textContent ?? ''),
      ).toBe(note);
    }
  });
});
