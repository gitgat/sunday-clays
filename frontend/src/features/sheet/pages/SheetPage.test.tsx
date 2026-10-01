import { screen, within } from '@testing-library/react';
import { delay, http, HttpResponse } from 'msw';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { clearMe, setMe } from '../../../lib/me';
import { expectChartControls } from '../../../test/charts';
import { LAZY_CHART, LAZY_TEST_TIMEOUT } from '../../../test/lazyChart';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { homeMeta, meDetail, meRounds, seasonEvents } from '../../home/mocks';
import { insightFixture } from '../../insights/mocks';
import { newerText } from '../components/Masthead';
import { sheetExplainers } from '../explainers';
import { onThisDayPost, postFixture, sheetFixture, trophyPost } from '../mocks';
import { SHEET_PLACEMENT, SheetPage } from './SheetPage';

// The rail's turnout chart loads lazily: warm it once so findBy*'s budget never covers a cold import.
beforeAll(async () => {
  await import('../../home/components/TurnoutChart');
});
const turnoutChart = () => screen.findByRole('region', { name: 'Turnout per Sunday' }, LAZY_CHART);

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

  it('says there is no Sheet yet at / on a fresh install, and keeps the rail', async () => {
    server.use(
      http.get('*/api/sheet/latest', () =>
        HttpResponse.json(
          { error: { code: 'sheet_not_found', message: 'No Sunday Sheet' } },
          { status: 404 },
        ),
      ),
    );
    server.use(
      http.get('*/api/meta', () => HttpResponse.json({ ...homeMeta, last_score_date: null })),
    );
    renderWithProviders(<SheetPage />, { route: '/', path: '/' });
    expect(await screen.findByText('No Sunday Sheet yet')).toBeInTheDocument();
    expect(await screen.findByText('An admin can upload the scores workbook.')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1, name: 'The Sunday Sheet' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'All Sundays' })).toHaveAttribute('href', '/events');
    expect(screen.queryByRole('link', { name: 'Latest issue' })).toBeNull();
    expect(screen.queryByText('No Sunday Sheet for this date')).toBeNull();
    expect(screen.getByRole('region', { name: 'Which one are you?' })).toBeInTheDocument();
    expect(await screen.findByRole('region', { name: 'Next Sunday' })).toBeInTheDocument();
  });

  it('does not say to upload the workbook when Sundays with partial results already exist', async () => {
    server.use(
      http.get('*/api/sheet/latest', () =>
        HttpResponse.json(
          { error: { code: 'sheet_not_found', message: 'No Sunday Sheet' } },
          { status: 404 },
        ),
      ),
    );
    renderWithProviders(<SheetPage />, { route: '/', path: '/' });
    expect(await screen.findByText('No Sunday has full results yet.')).toBeInTheDocument();
    expect(screen.queryByText(/upload the scores workbook/)).toBeNull();
  });

  it.each(['/sheet/2026-9-27', '/sheet/2026-13-01', '/sheet/not-a-date'])(
    'shows the not-found state, not a retry message, for the malformed date %s',
    async (route) => {
      server.use(
        http.get('*/api/sheet/:date', () =>
          HttpResponse.json(
            { error: { code: 'validation_error', message: 'bad date' } },
            { status: 422 },
          ),
        ),
      );
      renderAt(route);
      expect(await screen.findByText('No Sunday Sheet for this date')).toBeInTheDocument();
      expect(screen.queryByText('Try again in a moment.')).toBeNull();
      expect(screen.getByRole('link', { name: 'Latest issue' })).toHaveAttribute('href', '/');
      expect(
        screen.getByRole('heading', { level: 1, name: 'The Sunday Sheet' }),
      ).toBeInTheDocument();
    },
  );

  it('keeps an h1 on the dated not-found and the error states', async () => {
    server.use(
      http.get('*/api/sheet/:date', () =>
        HttpResponse.json({ error: { code: 'internal', message: 'Boom' } }, { status: 500 }),
      ),
    );
    renderAt();
    expect(await screen.findByText("Couldn't load the Sunday Sheet")).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1, name: 'The Sunday Sheet' })).toBeInTheDocument();
  });

  it('moves focus to the new card after "Not me", a pick and a skip', async () => {
    setMe(3);
    const { user } = renderAt();
    const panel = await screen.findByRole('region', { name: 'Your Sunday' });
    await user.click(within(panel).getByRole('button', { name: 'Not me' }));
    expect(screen.getByRole('heading', { name: 'Which one are you?' })).toHaveFocus();
    await user.type(screen.getByLabelText('Your name'), 'Hadley');
    await user.click(await screen.findByRole('button', { name: 'Hadley, Ike' }));
    expect(await screen.findByRole('heading', { name: 'Your Sunday' })).toHaveFocus();
    await user.click(
      within(screen.getByRole('region', { name: 'Your Sunday' })).getByRole('button', {
        name: 'Not me',
      }),
    );
    await user.click(screen.getByRole('button', { name: 'Not a shooter / skip' }));
    expect(screen.queryByRole('heading', { name: 'Which one are you?' })).toBeNull();
    const main = document.querySelector('[data-sheet-column="main"]') as HTMLElement;
    expect(main.contains(document.activeElement)).toBe(true);
    expect(document.activeElement?.tagName).toMatch(/^H\d$/);
  });

  it('gives Your Sunday and the rail their own complementary landmarks', async () => {
    renderAt();
    await screen.findByRole('heading', { level: 1, name: 'The Sunday Sheet' });
    const asides = screen.getAllByRole('complementary');
    expect(asides.map((a) => a.getAttribute('aria-label'))).toEqual([
      'Personal',
      'More about this Sunday',
    ]);
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

  it(
    'puts the blocks in the DOM in phone order, with the desktop columns placed explicitly',
    async () => {
      const { container } = renderAt();
      await turnoutChart();
      const blocks = [...container.querySelectorAll<HTMLElement>('[data-sheet-block]')];
      expect(blocks.map((b) => b.dataset['sheetBlock'])).toEqual([
        'masthead',
        'numbers',
        'you',
        'lead',
        'feed',
        'more',
        'next',
        'pulse',
        'details',
      ]);
      for (const [i, a] of blocks.entries()) {
        const b = blocks[i + 1];
        if (b === undefined) break;
        expect(
          Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING),
          `${a.dataset['sheetBlock'] ?? ''} before ${b.dataset['sheetBlock'] ?? ''}`,
        ).toBe(true);
      }
      for (const name of ['masthead', 'numbers', 'you'] as const) {
        const el = container.querySelector(`[data-sheet-block="${name}"]`);
        expect(el?.className, name).toContain(SHEET_PLACEMENT[name]);
      }
      for (const name of ['main', 'rail'] as const) {
        const el = container.querySelector(`[data-sheet-column="${name}"]`);
        expect(el?.className, name).toContain(SHEET_PLACEMENT[name]);
      }
      const you = container.querySelector('[data-sheet-block="you"]') as HTMLElement;
      const main = container.querySelector('[data-sheet-column="main"]') as HTMLElement;
      const rail = container.querySelector('[data-sheet-column="rail"]') as HTMLElement;
      expect(you.compareDocumentPosition(main) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      expect(main.compareDocumentPosition(rail) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      expect(container.innerHTML).not.toMatch(/(?:^|[ "])order-\d|\bcontents\b/);
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'keeps every former Home piece: numbers, lead, posts, Your Sunday, Next Sunday, Club pulse and details',
    async () => {
      setMe(3);
      server.use(
        http.get('*/api/sheet/:date', () =>
          HttpResponse.json(
            sheetFixture({
              headline: insightFixture({ key: 'hero' }),
              recap: insightFixture({
                key: 'recap',
                kind: 'home.sunday-recap',
                headline: [{ t: 'text', v: '23 shooters came out.' }],
                headline_you: null,
              }),
              spotlight: insightFixture({ key: 'spot', subject_id: '5' }),
            }),
          ),
        ),
        http.get('*/api/events', () => HttpResponse.json(seasonEvents)),
        http.get('*/api/shooters/:id', () => HttpResponse.json(meDetail)),
        http.get('*/api/shooters/:id/rounds', () => HttpResponse.json(meRounds)),
      );
      renderAt();
      expect(await screen.findByRole('region', { name: 'This Sunday in numbers' })).toBeVisible();
      expect(screen.getByRole('list', { name: 'Top story' })).toBeInTheDocument();
      expect(screen.getByText('23 shooters came out.')).toBeInTheDocument();
      expect(screen.getByRole('region', { name: 'Spotlight' })).toBeInTheDocument();
      expect(screen.getByRole('list', { name: 'Posts' })).toBeInTheDocument();
      const you = await screen.findByRole('region', { name: 'Your Sunday' });
      expect(await within(you).findByText('37 · 16th')).toBeInTheDocument();
      expect(await screen.findByRole('region', { name: 'Next Sunday' })).toBeVisible();
      expect(screen.getByRole('region', { name: 'Club pulse' })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'Full results, Sep 27, 2026' })).toHaveAttribute(
        'href',
        '/events/2026-09-27',
      );
      await turnoutChart();
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'gives every chart on the Sheet Table and CSV, and the turnout chart is its only one',
    async () => {
      renderAt();
      expectChartControls(await turnoutChart());
      expect(screen.getAllByRole('button', { name: 'CSV' })).toHaveLength(1);
      expect(screen.getAllByRole('button', { name: 'Table' })).toHaveLength(1);
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'asks for the club pulse of the 8 weeks up to the issue’s Sunday',
    async () => {
      const seen: string[] = [];
      server.use(
        http.get('*/api/events', ({ request }) => {
          const q = new URL(request.url).searchParams;
          seen.push(`${q.get('from') ?? ''}..${q.get('to') ?? ''}`);
          return HttpResponse.json(seasonEvents);
        }),
      );
      renderAt();
      await turnoutChart();
      expect(seen[0]).toBe('2026-08-03..2026-09-27');
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'shows Next Sunday on the latest issue only',
    async () => {
      server.use(
        http.get('*/api/sheet/:date', () =>
          HttpResponse.json(
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
          ),
        ),
      );
      const { container } = renderAt('/sheet/2026-09-13');
      await turnoutChart();
      expect(container.querySelector('[data-sheet-block="next"]')).toBeNull();
      expect(screen.getByRole('region', { name: 'Sunday details' })).toBeInTheDocument();
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'asks "Which one are you?", then fills Your Sunday, and "Not me" asks again',
    async () => {
      server.use(
        http.get('*/api/shooters', () =>
          HttpResponse.json([{ ...meDetail, shooter_id: 3, display_name: 'Hadley, Ike' }]),
        ),
        http.get('*/api/shooters/:id', () => HttpResponse.json(meDetail)),
        http.get('*/api/shooters/:id/rounds', () => HttpResponse.json(meRounds)),
      );
      const { user } = renderAt();
      const ask = await screen.findByRole('region', { name: 'Which one are you?' });
      await user.type(within(ask).getByLabelText('Your name'), 'Hadley');
      await user.click(await within(ask).findByRole('button', { name: 'Hadley, Ike' }));
      const you = await screen.findByRole('region', { name: 'Your Sunday' });
      await user.click(within(you).getByRole('button', { name: 'Not me' }));
      expect(await screen.findByRole('region', { name: 'Which one are you?' })).toBeInTheDocument();
      await turnoutChart();
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'drops the empty Your Sunday block when skipped, so the rail starts level with the main column',
    async () => {
      localStorage.setItem('sc.me.skip', '1');
      const { container } = renderAt();
      await turnoutChart();
      expect(container.querySelector('[data-sheet-block="you"]')).toBeNull();
      const rail = container.querySelector('[data-sheet-column="rail"]');
      expect(rail?.className).toContain('lg:row-start-3');
      expect(rail?.className).toContain('lg:row-span-2');
      expect(rail?.className).not.toContain('lg:row-start-4');
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'hides the question after "skip", also on the next visit',
    async () => {
      const first = renderAt();
      await first.user.click(await screen.findByRole('button', { name: 'Not a shooter / skip' }));
      expect(screen.queryByRole('region', { name: 'Which one are you?' })).toBeNull();
      await turnoutChart();
      first.unmount();
      renderAt();
      await turnoutChart();
      expect(screen.queryByRole('region', { name: 'Which one are you?' })).toBeNull();
    },
    LAZY_TEST_TIMEOUT,
  );

  const pastIssue = (headline = insightFixture({ key: 'hero' })) =>
    http.get('*/api/sheet/:date', () =>
      HttpResponse.json(
        sheetFixture({
          headline,
          masthead: {
            date: '2026-09-13',
            issue: 309,
            previous: '2026-09-06',
            next: '2026-09-27',
            latest: false,
            newer: null,
          },
        }),
      ),
    );

  it(
    'fixes the club pulse to the 8 weeks to the issue Sunday whatever the header window says',
    async () => {
      const seen: string[] = [];
      server.use(
        pastIssue(),
        http.get('*/api/events', ({ request }) => {
          const q = new URL(request.url).searchParams;
          seen.push(`${q.get('from') ?? ''}..${q.get('to') ?? ''}`);
          return HttpResponse.json(seasonEvents);
        }),
      );
      const { user } = renderAt('/sheet/2026-09-13?w=all');
      await turnoutChart();
      const pulse = screen.getByRole('region', { name: 'Club pulse' });
      expect(
        within(pulse).getByText('8 weeks to Sep 13, 2026 · not affected by the time filter'),
      ).toBeInTheDocument();
      expect(seen[0]).toBe('2026-07-20..2026-09-13');
      // The table's trimmed-window note names the 8 weeks, not the (ignored) time window.
      await user.click(
        within(screen.getByRole('region', { name: 'Turnout per Sunday' })).getByRole('button', {
          name: 'Table',
        }),
      );
      expect(await screen.findByText(/Showing these 8 weeks\./)).toBeInTheDocument();
    },
    LAZY_TEST_TIMEOUT,
  );

  it('dates the Top story only when the headline is about an earlier Sunday than the issue', async () => {
    server.use(pastIssue(insightFixture({ key: 'hero', anchor_date: '2026-09-13' })));
    const first = renderAt('/sheet/2026-09-13');
    const top = await screen.findByRole('region', { name: 'Top story' });
    expect(within(top).getByText('Not affected by the time filter')).toBeInTheDocument();
    first.unmount();
    server.use(pastIssue(insightFixture({ key: 'hero', anchor_date: '2026-09-06' })));
    renderAt('/sheet/2026-09-13');
    const older = await screen.findByRole('region', { name: 'Top story' });
    expect(
      within(older).getByText('Sep 6, 2026 · not affected by the time filter'),
    ).toBeInTheDocument();
  });

  it(
    'keeps the Club pulse card, with no widen buttons, when the 8 weeks hold no scored Sundays',
    async () => {
      server.use(http.get('*/api/events', () => HttpResponse.json([])));
      renderAt('/sheet/2026-09-27?w=12m');
      expect(await screen.findByText('No scored Sundays in these 8 weeks')).toBeInTheDocument();
      const pulse = screen.getByRole('region', { name: 'Club pulse' });
      expect(
        within(pulse).getByText('8 weeks to Sep 27, 2026 · not affected by the time filter'),
      ).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /12M|all time/i })).toBeNull();
      expect(screen.queryByText(/last 12 months/)).toBeNull();
    },
    LAZY_TEST_TIMEOUT,
  );
});
