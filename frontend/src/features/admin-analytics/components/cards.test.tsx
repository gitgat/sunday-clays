import { screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  captureCsv,
  chartOptionIn,
  expectChartControls,
  expectExplainer,
  openFullscreen,
} from '../../../test/charts';
import { LAZY_CHART, LAZY_TEST_TIMEOUT } from '../../../test/lazyChart';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import type { AnalyticsRange } from '../api';
import { bumps, pageKinds, uptake, visitors } from '../mocks';
import { BumpsCard } from './BumpsCard';
import { PageKindsCard } from './PageKindsCard';
import { UptakeCard } from './UptakeCard';
import { VisitorsCard } from './VisitorsCard';

const RANGE: AnalyticsRange = { since: '2026-08-07', asOf: '2026-10-01' };

afterEach(() => {
  vi.restoreAllMocks();
});

async function region(name: string): Promise<HTMLElement> {
  // The titled card exists while loading; wait for the chart frame's own controls.
  return waitFor(() => {
    const found = screen.getByRole('region', { name });
    within(found).getByRole('button', { name: 'Table' });
    return found;
  }, LAZY_CHART);
}

describe('VisitorsCard', () => {
  it(
    'charts devices per day with Table, CSV, fullscreen and an explainer, and lists the busiest days',
    async () => {
      renderWithProviders(<VisitorsCard range={RANGE} />);
      const card = await region('Visitors');
      expectChartControls(card);
      expect(within(card).getByRole('button', { name: 'Fullscreen' })).toBeInTheDocument();
      await expectExplainer(card, 'About this chart', { read: true });
      const busiest = screen.getByRole('list', { name: 'Busiest days' });
      expect(
        within(busiest)
          .getAllByRole('listitem')
          .map((li) => li.textContent),
      ).toEqual(['Sep 27, 202614 devices', 'Sep 30, 20264 devices', 'Sep 28, 20263 devices']);
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'switches to weeks',
    async () => {
      const { user } = renderWithProviders(<VisitorsCard range={RANGE} />);
      const card = await region('Visitors');
      await user.click(within(card).getByRole('button', { name: 'Per week' }));
      expect(within(card).getByRole('button', { name: 'Per week' })).toHaveAttribute(
        'aria-pressed',
        'true',
      );
      await user.click(within(card).getByRole('button', { name: 'Table' }));
      expect(within(card).getByRole('columnheader', { name: 'Week of' })).toBeInTheDocument();
      expect(within(card).getAllByRole('row')).toHaveLength(3);
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'opens fullscreen and downloads the CSV from all time (no since)',
    async () => {
      const seen: (string | null)[] = [];
      server.use(
        http.get('*/api/admin/analytics/visitors', ({ request }) => {
          seen.push(new URL(request.url).searchParams.get('since'));
          return HttpResponse.json(visitors);
        }),
      );
      const csv = captureCsv();
      const { user } = renderWithProviders(<VisitorsCard range={RANGE} />);
      const card = await region('Visitors');
      const dialog = await openFullscreen(user, card, 'Visitors');
      expect(await within(dialog).findByText('Every day on record.')).toBeInTheDocument();
      await user.click(within(dialog).getByRole('button', { name: 'CSV' }));
      await waitFor(() => expect(csv.names).toEqual(['visitors-day-2026-10-01.csv']));
      expect(seen).toEqual(['2026-08-07', null]);
    },
    LAZY_TEST_TIMEOUT,
  );

  it('says why when the server refuses', async () => {
    server.use(
      http.get('*/api/admin/analytics/visitors', () =>
        HttpResponse.json(
          { error: { code: 'forbidden', message: 'Admin access required' } },
          { status: 403 },
        ),
      ),
    );
    renderWithProviders(<VisitorsCard range={RANGE} />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Admins only');
  });

  it('shows an empty state when nothing was counted', async () => {
    server.use(
      http.get('*/api/admin/analytics/visitors', () =>
        HttpResponse.json({ days: [], weeks: [], busiest: [] }),
      ),
    );
    renderWithProviders(<VisitorsCard range={{ since: null, asOf: '2026-10-01' }} />);
    expect(await screen.findByText('Nothing counted in this window yet.')).toBeInTheDocument();
  });
});

describe('an empty database', () => {
  // The API zero-fills a single day (since clamped to as_of), so there are rows but no counts.
  it('says nothing was counted instead of drawing flat charts', async () => {
    server.use(
      http.get('*/api/admin/analytics/pages', () => HttpResponse.json([])),
      http.get('*/api/admin/analytics/visitors', () =>
        HttpResponse.json({
          days: [{ day: '2026-10-01', devices: 0 }],
          weeks: [{ week: '2026-09-28', devices: 0 }],
          busiest: [],
        }),
      ),
      http.get('*/api/admin/analytics/bumps', () =>
        HttpResponse.json({
          days: [{ day: '2026-10-01', bumps: 0 }],
          top: [],
          devices: 0,
          devices_all_time: 0,
        }),
      ),
      http.get('*/api/admin/analytics/me-states', () =>
        HttpResponse.json({
          weeks: [{ week: '2026-09-28', picked: 0, skipped: 0, none: 0 }],
          latest: { picked: 0, skipped: 0, none: 0 },
          latest_since: null,
        }),
      ),
    );
    renderWithProviders(
      <>
        <VisitorsCard range={RANGE} />
        <BumpsCard range={RANGE} />
        <UptakeCard range={RANGE} />
        <PageKindsCard range={RANGE} />
      </>,
    );
    await waitFor(
      () => expect(screen.getAllByText('Nothing counted in this window yet.')).toHaveLength(4),
      LAZY_CHART,
    );
    expect(screen.queryByRole('button', { name: 'Table' })).not.toBeInTheDocument();
  });
});

describe('PageKindsCard', () => {
  it(
    'charts views per page kind in plain words',
    async () => {
      renderWithProviders(<PageKindsCard range={RANGE} />);
      const card = await region('Page views by page');
      expectChartControls(card);
      await expectExplainer(card, 'About this chart', { read: true });
      const option = chartOptionIn(card, 'Page views by page');
      expect((option.yAxis as { data: string[] }[])[0]?.data).toEqual([
        'Home',
        'Shooter profiles',
        'One Sunday',
        'Leaderboards',
      ]);
    },
    LAZY_TEST_TIMEOUT,
  );
});

describe('BumpsCard', () => {
  it(
    'charts bumps per day, says how many devices bumped and lists the most-bumped insights',
    async () => {
      renderWithProviders(<BumpsCard range={RANGE} />);
      const card = await region('Fist bumps per day');
      expectChartControls(card);
      await expectExplainer(card, 'About this chart', { read: true });
      expect(within(card).getByText('8 devices bumped in this window · 12 all time')).toBeVisible();
      const top = screen.getByRole('list', { name: 'Most-bumped insights' });
      expect(
        within(top)
          .getAllByRole('listitem')
          .map((li) => li.textContent),
      ).toEqual([
        'Ike Hadley broke 45 for the first time6 bumps',
        'An insight no longer on the site1 bump',
      ]);
    },
    LAZY_TEST_TIMEOUT,
  );

  it('says when nothing was bumped', async () => {
    server.use(
      http.get('*/api/admin/analytics/bumps', () =>
        HttpResponse.json({ ...bumps, top: [], devices: 1, devices_all_time: 1 }),
      ),
    );
    renderWithProviders(<BumpsCard range={RANGE} />);
    expect(await screen.findByText('No bumps in this window yet.')).toBeInTheDocument();
    expect(
      await screen.findByText('1 device bumped in this window · 1 all time'),
    ).toBeInTheDocument();
  });
});

describe('UptakeCard', () => {
  it(
    'stacks the answers per week and sums up each device’s last answer',
    async () => {
      renderWithProviders(<UptakeCard range={RANGE} />);
      const card = await region('“Which one are you?” answers');
      expectChartControls(card);
      await expectExplainer(card, 'About this chart', { read: true });
      expect(
        within(card).getByText(
          'Last answer of each device since Jul 3, 2026: 11 picked a name, 3 skipped, 8 not answered',
        ),
      ).toBeVisible();
    },
    LAZY_TEST_TIMEOUT,
  );

  it('says when no visits are kept in detail', async () => {
    server.use(
      http.get('*/api/admin/analytics/me-states', () =>
        HttpResponse.json({
          ...uptake,
          latest: { picked: 0, skipped: 0, none: 0 },
          latest_since: null,
        }),
      ),
    );
    renderWithProviders(<UptakeCard range={RANGE} />);
    expect(
      await screen.findByText('No visits in this window are kept in detail.', {}, LAZY_CHART),
    ).toBeInTheDocument();
  });
});

describe.each([
  ['visitors', 'Visitors', 'Every day on record.', 'visitors-day', visitors, VisitorsCard],
  ['pages', 'Page views by page', 'Every day on record.', 'page-views', pageKinds, PageKindsCard],
  ['bumps', 'Fist bumps per day', 'Every day on record.', 'fist-bumps', bumps, BumpsCard],
  [
    'me-states',
    '“Which one are you?” answers',
    'Every week on record.',
    'which-one-are-you',
    uptake,
    UptakeCard,
  ],
] as const)('%s card: window and all-time reads', (name, title, note, csvPrefix, body, Card) => {
  it(
    'reads the window for the chart and all time for fullscreen and the CSV',
    async () => {
      const seen: (string | null)[] = [];
      server.use(
        http.get(`*/api/admin/analytics/${name}`, ({ request }) => {
          seen.push(new URL(request.url).searchParams.get('since'));
          return HttpResponse.json(body);
        }),
      );
      const csv = captureCsv();
      const { user } = renderWithProviders(<Card range={RANGE} />);
      const card = await region(title);
      const dialog = await openFullscreen(user, card, title);
      expect(await within(dialog).findByText(note)).toBeInTheDocument();
      await user.click(within(dialog).getByRole('button', { name: 'CSV' }));
      await waitFor(() => expect(csv.names).toEqual([`${csvPrefix}-2026-10-01.csv`]));
      expect(seen).toEqual(['2026-08-07', null]);
    },
    LAZY_TEST_TIMEOUT,
  );

  it('says why when the server refuses', async () => {
    server.use(
      http.get(`*/api/admin/analytics/${name}`, () =>
        HttpResponse.json(
          { error: { code: 'forbidden', message: 'Admin access required' } },
          { status: 403 },
        ),
      ),
    );
    renderWithProviders(<Card range={RANGE} />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Admins only');
  });
});
