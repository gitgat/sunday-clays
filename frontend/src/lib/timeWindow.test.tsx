import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../test/msw/server';
import { renderWithProviders } from '../test/render';
import { useRoundTypeHref, useRoundTypeLink, withRoundTypes } from './roundTypes';
import {
  CUSTOM_SHORT_LABEL,
  DEFAULT_WINDOW,
  customWindow,
  filterRowsByWindow,
  isCustomWindow,
  pageDefaultWindow,
  parseCustomWindow,
  useTimeWindow,
  useWindowChoice,
  windowCodec,
  windowLabel,
  windowRange,
  zoomToWindow,
} from './timeWindow';

describe('windowCodec', () => {
  it('reads known values and rejects unknown ones', () => {
    expect(windowCodec.parse('6m')).toBe('6m');
    expect(windowCodec.parse('8w')).toBe('8w');
    expect(windowCodec.parse('ytd')).toBe('ytd');
    expect(windowCodec.parse('2y')).toBeNull();
  });

  it('reads the retired calendar-season value as unknown, so it falls back to the default 8 weeks', () => {
    expect(windowCodec.parse('season')).toBeNull();
  });

  it('defaults to the last 8 weeks', () => {
    expect(DEFAULT_WINDOW).toBe('8w');
  });
});

describe('the Custom window', () => {
  it('parses a valid custom value and round-trips it', () => {
    expect(windowCodec.parse('2025-03-01..2025-09-28')).toBe('2025-03-01..2025-09-28');
    expect(windowCodec.serialize('2025-03-01..2025-09-28')).toBe('2025-03-01..2025-09-28');
    expect(windowCodec.parse('2025-09-28..2025-09-28')).toBe('2025-09-28..2025-09-28');
  });

  it.each([
    '2025-09-28..2025-03-01',
    '2026-02-30..2026-03-01',
    '..',
    '2026-01-01..',
    '..2026-01-01',
    '2026-01-01',
    '2026-1-1..2026-2-1',
    '2026-01-01..2026-02-01..2026-03-01',
  ])('rejects %s, so it reads as the default', (raw) => {
    expect(windowCodec.parse(raw)).toBeNull();
  });

  it('builds, detects and parses custom windows', () => {
    const w = customWindow('2025-03-01', '2025-09-28');
    expect(w).toBe('2025-03-01..2025-09-28');
    expect(isCustomWindow(w)).toBe(true);
    expect(isCustomWindow('3m')).toBe(false);
    expect(parseCustomWindow(w)).toEqual({ from: '2025-03-01', to: '2025-09-28' });
    expect(parseCustomWindow('3m')).toBeNull();
    expect(CUSTOM_SHORT_LABEL).toBe('Custom');
  });

  it('labels a custom window with its dates and ranges it exactly, ignoring the anchor', () => {
    const w = customWindow('2025-03-01', '2025-09-28');
    expect(windowLabel(w)).toBe('Mar 1, 2025 – Sep 28, 2025');
    expect(windowRange(w, '2026-09-27')).toEqual({ from: '2025-03-01', to: '2025-09-28' });
  });

  it('filters rows and zooms a chart to a custom range', () => {
    const range = windowRange(customWindow('2025-03-01', '2025-09-28'), '2026-09-27');
    const rows = [
      { d: '2025-02-28' },
      { d: '2025-03-01' },
      { d: '2025-09-28' },
      { d: '2025-09-29' },
    ];
    expect(filterRowsByWindow(rows, 'd', range).map((r) => r.d)).toEqual([
      '2025-03-01',
      '2025-09-28',
    ]);
    expect(
      zoomToWindow({ xAxis: { type: 'time' as const }, yAxis: {}, series: [] }, range).dataZoom,
    ).toEqual([{ type: 'inside', startValue: '2025-03-01', endValue: '2025-09-28' }]);
  });

  it('is carried by in-app links, and no window in the URL adds none', () => {
    expect(withRoundTypes('/x', [], '2025-03-01..2025-09-28')).toBe('/x?w=2025-03-01..2025-09-28');
    expect(withRoundTypes('/x', [], null)).toBe('/x');
    expect(withRoundTypes('/x', [])).toBe('/x');
  });
});

describe('windowRange', () => {
  it.each([
    ['3m', '2026-09-27', '2026-06-28'],
    ['6m', '2026-09-27', '2026-03-28'],
    ['12m', '2026-09-27', '2025-09-28'],
    ['3m', '2026-05-31', '2026-03-01'],
    ['3m', '2026-01-04', '2025-10-05'],
    ['12m', '2028-02-29', '2027-03-01'],
    ['8w', '2026-09-27', '2026-08-03'],
    ['8w', '2026-01-04', '2025-11-10'],
    ['8w', '2028-03-05', '2028-01-10'],
    ['ytd', '2026-09-27', '2026-01-01'],
    ['ytd', '2026-01-04', '2026-01-01'],
    ['all', '2026-09-27', null],
  ] as const)('%s from %s starts at %s', (w, anchor, from) => {
    expect(windowRange(w, anchor)).toEqual({ from, to: anchor });
  });
});

describe('windowLabel', () => {
  it('names each window', () => {
    expect((['8w', '3m', '6m', '12m', 'ytd', 'all'] as const).map((w) => windowLabel(w))).toEqual([
      'Last 8 weeks',
      'Last 3 months',
      'Last 6 months',
      'Last 12 months',
      'This year to date',
      'All time',
    ]);
  });
});

describe('filterRowsByWindow', () => {
  const rows = [
    { d: '2026-06-27', v: 1 },
    { d: '2026-06-28', v: 2 },
    { d: '2026-09-27T00:00:00', v: 3 },
    { d: '2026-10-04', v: 4 },
    { d: null, v: 5 },
  ];
  it('keeps rows inside the inclusive range', () => {
    expect(
      filterRowsByWindow(rows, 'd', { from: '2026-06-28', to: '2026-09-27' }).map((r) => r.v),
    ).toEqual([2, 3]);
  });
  it('has no lower bound when from is null', () => {
    expect(filterRowsByWindow(rows, 'd', { from: null, to: '2026-09-27' }).map((r) => r.v)).toEqual(
      [1, 2, 3],
    );
  });
});

describe('zoomToWindow', () => {
  const range = { from: '2026-06-28', to: '2026-09-27' };
  it('zooms a time axis to the range', () => {
    const option = { xAxis: { type: 'time' as const }, yAxis: {}, series: [] };
    expect(zoomToWindow(option, range).dataZoom).toEqual([
      { type: 'inside', startValue: '2026-06-28', endValue: '2026-09-27' },
    ]);
  });
  it('zooms a category axis of dates by index', () => {
    const option = {
      xAxis: [
        {
          type: 'category' as const,
          data: ['2026-06-21', '2026-06-28', '2026-07-05', '2026-10-04'],
        },
      ],
      yAxis: {},
    };
    expect(zoomToWindow(option, range).dataZoom).toEqual([
      { type: 'inside', startValue: 1, endValue: 2 },
    ]);
  });
  it('zooms a category axis of months, keeping the months the range touches', () => {
    const option = {
      xAxis: {
        type: 'category' as const,
        data: ['2026-05', '2026-06', '2026-07', '2026-09', '2026-10'],
      },
      yAxis: {},
    };
    expect(zoomToWindow(option, range).dataZoom).toEqual([
      { type: 'inside', startValue: 1, endValue: 3 },
    ]);
  });
  it('leaves the option alone when nothing falls in the window', () => {
    const option = { xAxis: { type: 'category' as const, data: ['2020-01-05', 7] }, yAxis: {} };
    expect(zoomToWindow(option, range)).toBe(option);
  });
  it('leaves a category axis that is not dates alone', () => {
    const option = { xAxis: { type: 'category' as const, data: ['20', '22', '38', '2026'] } };
    expect(zoomToWindow(option, range)).toBe(option);
  });
  it('leaves the option alone when the range is unbounded', () => {
    const option = { xAxis: { type: 'time' as const } };
    expect(zoomToWindow(option, { from: null, to: '2026-09-27' })).toBe(option);
  });
  it('leaves an option without a date axis alone', () => {
    const value = { xAxis: { type: 'value' as const } };
    const none = { series: [] };
    expect(zoomToWindow(value, range)).toBe(value);
    expect(zoomToWindow(none, range)).toBe(none);
  });
});

function Probe() {
  const { window, range, label, ready, setWindow } = useTimeWindow();
  return (
    <>
      <p>
        {window}|{label}|{String(ready)}|{range === null ? 'none' : `${range.from}..${range.to}`}
      </p>
      <button type="button" onClick={() => setWindow('6m')}>
        six
      </button>
    </>
  );
}

function Choice() {
  const [w] = useWindowChoice();
  return <p>choice:{w}</p>;
}

describe('useTimeWindow', () => {
  it('anchors on the latest scored Sunday, not the clock, and defaults to 8 weeks', async () => {
    server.use(http.get('*/api/meta', () => HttpResponse.json({ last_score_date: '2026-09-27' })));
    renderWithProviders(<Probe />);
    expect(await screen.findByText('8w|Last 8 weeks|true|2026-08-03..2026-09-27')).toBeVisible();
  });

  it('is not ready while nothing is scored, and writes only non-default values', async () => {
    server.use(http.get('*/api/meta', () => HttpResponse.json({ last_score_date: null })));
    const { user, router } = renderWithProviders(<Probe />);
    expect(await screen.findByText('8w|Last 8 weeks|false|none')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'six' }));
    expect(router.state.location.search).toBe('?w=6m');
  });

  it('has the range of a custom window straight away, before /api/meta answers', () => {
    server.use(http.get('*/api/meta', () => new Promise(() => undefined)));
    renderWithProviders(<Probe />, { route: '/?w=2025-03-01..2025-09-28' });
    expect(
      screen.getByText(
        '2025-03-01..2025-09-28|Mar 1, 2025 – Sep 28, 2025|true|2025-03-01..2025-09-28',
      ),
    ).toBeVisible();
  });

  it('has the range of a custom window when nothing is scored', async () => {
    server.use(http.get('*/api/meta', () => HttpResponse.json({ last_score_date: null })));
    renderWithProviders(<Probe />, { route: '/?w=2025-03-01..2025-09-28' });
    expect(
      await screen.findByText(
        '2025-03-01..2025-09-28|Mar 1, 2025 – Sep 28, 2025|true|2025-03-01..2025-09-28',
      ),
    ).toBeVisible();
  });

  it('reads an invalid custom value as the default', async () => {
    server.use(http.get('*/api/meta', () => HttpResponse.json({ last_score_date: '2026-09-27' })));
    renderWithProviders(<Probe />, { route: '/?w=2025-09-28..2025-03-01' });
    expect(await screen.findByText('8w|Last 8 weeks|true|2026-08-03..2026-09-27')).toBeVisible();
  });

  it('reads the window from the URL, the default for an unknown value', () => {
    renderWithProviders(<Choice />, { route: '/?w=all' });
    expect(screen.getByText('choice:all')).toBeVisible();
  });
});

function Links() {
  const to = useRoundTypeLink('/club');
  const href = useRoundTypeHref()('/club');
  return (
    <>
      <p>link:{typeof to === 'string' ? to : to.search}</p>
      <p>href:{href}</p>
    </>
  );
}

describe('the per-page default window', () => {
  it('is 12 months on Weather and the Race and 8 weeks everywhere else', () => {
    expect(pageDefaultWindow('/race')).toBe('12m');
    expect(pageDefaultWindow('/records')).toBe('8w');
    expect(pageDefaultWindow('/weather')).toBe('12m');
    expect(pageDefaultWindow('/weather/')).toBe('12m');
    expect(pageDefaultWindow('/club')).toBe('8w');
    expect(pageDefaultWindow('/')).toBe('8w');
  });

  it('applies only when the URL has no w', () => {
    renderWithProviders(<Choice />, { route: '/weather' });
    expect(screen.getByText('choice:12m')).toBeVisible();
  });

  it('lets an explicit w win, including the global default spelled out', () => {
    renderWithProviders(<Choice />, { route: '/weather?w=8w' });
    expect(screen.getByText('choice:8w')).toBeVisible();
  });

  it('ranges the page default from the anchor and writes a non-default choice', async () => {
    server.use(http.get('*/api/meta', () => HttpResponse.json({ last_score_date: '2026-09-27' })));
    const { user, router } = renderWithProviders(<Probe />, { route: '/weather' });
    expect(await screen.findByText('12m|Last 12 months|true|2025-09-28..2026-09-27')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'six' }));
    expect(router.state.location.search).toBe('?w=6m');
  });

  it('keeps an explicit 8W on links, so Weather does not swap it for its 12M', () => {
    expect(withRoundTypes('/weather', [], '8w')).toBe('/weather?w=8w');
  });

  it('never turns a page default into a link param', () => {
    renderWithProviders(<Links />, { route: '/weather' });
    expect(screen.getByText('link:')).toBeVisible();
    expect(screen.getByText('href:/club')).toBeVisible();
  });

  it('carries an explicit w on links from any page', () => {
    renderWithProviders(<Links />, { route: '/club?w=8w' });
    expect(screen.getByText('link:?w=8w')).toBeVisible();
    expect(screen.getByText('href:/club?w=8w')).toBeVisible();
  });

  it('carries a non-default explicit w from Weather', () => {
    renderWithProviders(<Links />, { route: '/weather?w=6m' });
    expect(screen.getByText('link:?w=6m')).toBeVisible();
  });

  it('reads an invalid w as none', () => {
    renderWithProviders(<Links />, { route: '/club?w=zzz' });
    expect(screen.getByText('link:')).toBeVisible();
  });
});
