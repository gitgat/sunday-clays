import { describe, expect, it } from 'vitest';
import type { InsightChart } from './api';
import { chartHref, explorerParams, highlightItems } from './chartLink';
import { insightFixture } from './mocks';

const page = insightFixture().chart;

function explorer(overrides: Partial<InsightChart> = {}): InsightChart {
  return {
    ...page,
    type: 'explorer',
    route: null,
    anchor: null,
    params: {},
    chart_type: 'bar',
    highlight: { shooter_ids: [3] },
    ref: 0,
    spec: {
      metric: 'adjusted',
      agg: 'avg',
      group_by: ['precip_band'],
      sort: 'key_asc',
      limit: 500,
      filters: {
        date_from: '2024-01-07',
        date_to: '2026-09-27',
        shooter_ids: [3],
        round_types: [],
        statuses: [],
        gauges: [],
        min_rounds: 0,
        best_round_only: true,
        min_score: null,
        ytd: null,
      },
    },
    ...overrides,
  };
}

describe('highlightItems', () => {
  it('lists dates, shooters, keys and a span', () => {
    expect(
      highlightItems({
        dates: ['2026-09-27'],
        shooter_ids: [3, 4],
        keys: ['wet'],
        span: ['2026-08-02', '2026-09-27'],
      }),
    ).toEqual(['2026-09-27', 's:3', 's:4', 'wet', '2026-08-02..2026-09-27']);
  });
});

describe('chartHref', () => {
  it('links a page chart with its highlight, dates and options, anchored to the card', () => {
    expect(chartHref(page)).toBe(
      '/shooters/3?trend.hl=2026-09-27&trend.from=2026-06-27&trend.to=2026-09-27' +
        '&w=2026-06-27..2026-09-27&trend.line=pb#chart-trend',
    );
  });

  it('builds the Explorer query with an explicit window and no round-type filter', () => {
    const href = chartHref(explorer());
    const params = new URLSearchParams(href.split('?')[1]);
    expect(href.startsWith('/explorer?')).toBe(true);
    expect(Object.fromEntries(params)).toEqual({
      m: 'adjusted',
      a: 'avg',
      g: 'precip_band',
      w: '2024-01-07..2026-09-27',
      sh: '3',
      best: '1',
      c: 'bar',
      'v.hl': 's:3',
      'v.ref': '0',
    });
    expect(params.has('rt')).toBe(false);
  });

  it('carries the minimum score as ms, and omits it when unset or absent', () => {
    const base = explorer();
    const spec = base.spec ?? null;
    if (spec === null) throw new Error('fixture has a spec');
    const withMs = chartHref(
      explorer({ spec: { ...spec, filters: { ...spec.filters, min_score: 40 } } }),
    );
    expect(new URLSearchParams(withMs.split('?')[1]).get('ms')).toBe('40');
    const rest: Partial<typeof spec.filters> = { ...spec.filters };
    delete rest.min_score;
    const absent = chartHref(explorer({ spec: { ...spec, filters: rest as typeof spec.filters } }));
    expect(new URLSearchParams(absent.split('?')[1]).has('ms')).toBe(false);
    expect(new URLSearchParams(chartHref(base).split('?')[1]).has('ms')).toBe(false);
  });

  it('turns a compare spec into cmp keys, "everyone" as an empty cmp.sh', () => {
    const base = explorer();
    const spec = base.spec ?? null;
    if (spec === null) throw new Error('fixture has a spec');
    const href = chartHref(
      explorer({
        compare: { ...spec, metric: 'score', filters: { ...spec.filters, shooter_ids: [] } },
      }),
    );
    const params = new URLSearchParams(href.split('?')[1]);
    expect(params.get('cmp.m')).toBe('score');
    expect(params.get('cmp.sh')).toBe('');
    expect(params.get('cmp.best')).toBe('1');
  });

  it('keeps metric and period as the leaderboard page own keys', () => {
    const href = chartHref({
      ...page,
      route: '/leaderboards',
      anchor: 'lb-board',
      params: { metric: 'rating_gain', period: 'season' },
      highlight: { shooter_ids: [9] },
    });
    expect(href).toContain('metric=rating_gain&period=season');
    expect(href).toContain('lb-board.hl=s%3A9');
    expect(href.endsWith('#chart-lb-board')).toBe(true);
  });
});

describe('the window a link opens on', () => {
  const spec = explorer().spec as NonNullable<InsightChart['spec']>;
  const undated = (chart: InsightChart) =>
    explorer({
      ...chart,
      spec: { ...spec, filters: { ...spec.filters, date_from: null, date_to: null } },
    });

  it('never sets From or To: the Explorer takes its dates from w', () => {
    const params = new URLSearchParams(chartHref(explorer()).split('?')[1]);
    expect(params.has('from')).toBe(false);
    expect(params.has('to')).toBe(false);
  });

  it('is a Custom window of the insight own dates, whatever the viewer had chosen', () => {
    const params = new URLSearchParams(chartHref(explorer(), '3m').split('?')[1]);
    expect(params.get('w')).toBe('2024-01-07..2026-09-27');
  });

  it('fills the missing end of a one-sided span from the insight window', () => {
    const from = explorer({
      spec: { ...spec, filters: { ...spec.filters, date_from: '2025-01-05', date_to: null } },
    });
    expect(new URLSearchParams(chartHref(from).split('?')[1]).get('w')).toBe(
      '2025-01-05..2026-09-27',
    );
    const to = explorer({
      spec: { ...spec, filters: { ...spec.filters, date_from: null, date_to: '2026-08-01' } },
    });
    expect(new URLSearchParams(chartHref(to).split('?')[1]).get('w')).toBe(
      '2026-06-27..2026-08-01',
    );
    // A span that would run backwards is no span: the viewer's window stays.
    const backwards = explorer({
      spec: { ...spec, filters: { ...spec.filters, date_from: null, date_to: '2025-03-02' } },
    });
    expect(new URLSearchParams(chartHref(backwards, '6m').split('?')[1]).get('w')).toBe('6m');
  });

  it('keeps the viewer window when the insight has no dates of its own', () => {
    const chart = undated(explorer());
    expect(new URLSearchParams(chartHref(chart, '12m').split('?')[1]).get('w')).toBe('12m');
    expect(
      new URLSearchParams(chartHref(chart, '2025-03-01..2025-09-28').split('?')[1]).get('w'),
    ).toBe('2025-03-01..2025-09-28');
    // An explicit 8W is the viewer's choice and travels; no window in the URL writes none.
    expect(new URLSearchParams(chartHref(chart, '8w').split('?')[1]).get('w')).toBe('8w');
    expect(new URLSearchParams(chartHref(chart).split('?')[1]).has('w')).toBe(false);
    expect(new URLSearchParams(chartHref(chart, null).split('?')[1]).has('w')).toBe(false);
  });

  it('spells an explicit viewer window out, 8W included, so it beats the destination default', () => {
    const weather = {
      ...page,
      route: '/weather',
      anchor: 'wf',
      window: { from: '2026-09-27', to: '2026-01-01' },
    };
    // A reversed insight window is no window at all; the viewer's 8W must not become Weather's 12M.
    expect(chartHref(weather, '8w')).toContain('w=8w');
    expect(chartHref(weather, '12m')).toContain('w=12m');
    // Nothing explicit in the URL: Weather keeps its own default.
    expect(chartHref(weather, null)).not.toContain('w=');
  });

  it('carries the viewer window to a bare Explorer link too', () => {
    expect(chartHref(explorer({ spec: null }), '6m')).toBe('/explorer?w=6m');
    expect(chartHref(explorer({ spec: null }), '8w')).toBe('/explorer?w=8w');
    expect(chartHref(explorer({ spec: null }), null)).toBe('/explorer');
  });
});

describe('explorerParams', () => {
  it('carries the year-to-date cut', () => {
    const spec = explorer().spec as NonNullable<InsightChart['spec']>;
    const withYtd = { ...spec, filters: { ...spec.filters, ytd: '09-27' } };
    expect(explorerParams(withYtd, null).get('ytd')).toBe('09-27');
    expect(explorerParams(spec, null).has('ytd')).toBe(false);
  });
});

describe('chartHref edge cases', () => {
  it('opens the bare Explorer without a spec', () => {
    expect(chartHref(explorer({ spec: null }))).toBe('/explorer');
    expect(chartHref(explorer({ spec: undefined }))).toBe('/explorer');
  });

  it('writes optional Explorer keys only when set', () => {
    const base = explorer().spec;
    if (base === null || base === undefined) throw new Error('fixture has a spec');
    const href = chartHref(
      explorer({
        ref: null,
        chart_type: null,
        highlight: {},
        spec: {
          ...base,
          sort: 'value_desc',
          filters: {
            ...base.filters,
            date_from: null,
            date_to: null,
            min_rounds: 5,
            best_round_only: false,
            shooter_ids: [],
          },
        },
        compare: {
          ...base,
          agg: 'max',
          filters: { ...base.filters, shooter_ids: [4, 5], best_round_only: false },
        },
      }),
    );
    const params = new URLSearchParams(href.split('?')[1]);
    expect(params.get('mr')).toBe('5');
    expect(params.get('s')).toBe('value_desc');
    expect(params.has('from')).toBe(false);
    expect(params.has('w')).toBe(false);
    expect(params.has('sh')).toBe(false);
    expect(params.has('best')).toBe(false);
    expect(params.has('c')).toBe(false);
    expect(params.has('v.hl')).toBe(false);
    expect(params.has('v.ref')).toBe(false);
    expect(params.get('cmp.a')).toBe('max');
    expect(params.get('cmp.sh')).toBe('4,5');
    expect(params.has('cmp.m')).toBe(false);
    expect(params.has('cmp.best')).toBe(false);
  });

  it('a page chart without route or anchor (never emitted by the backend) still builds a URL', () => {
    const href = chartHref({
      ...page,
      route: null,
      anchor: null,
      params: {},
      highlight: {},
      ref: 42,
    });
    expect(href.startsWith('/?')).toBe(true);
    expect(href).toContain('.ref=42');
  });

  it('skips an incomplete highlight span', () => {
    expect(highlightItems({ span: ['2026-08-02'] })).toEqual([]);
  });
});
