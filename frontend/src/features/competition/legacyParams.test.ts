import { describe, expect, it } from 'vitest';

import {
  convertLegacyBoard,
  convertLegacyMetric,
  convertLegacyRace,
  convertLegacyRecords,
  type LegacyContext,
} from './legacyParams';

const CTX: LegacyContext = {
  firstSunday: '2020-01-05',
  lastSunday: '2026-09-27',
  pageDefault: '8w',
};
const params = (query: string) => new URLSearchParams(query);

describe('convertLegacyMetric', () => {
  it.each(['rating', 'most_improved'])('turns %s into rating_gain', (metric) => {
    expect(convertLegacyMetric(params(`metric=${metric}`))).toEqual({ metric: 'rating_gain' });
  });

  it('leaves current and missing metrics alone', () => {
    expect(convertLegacyMetric(params('metric=wins'))).toEqual({});
    expect(convertLegacyMetric(params(''))).toEqual({});
  });
});

describe('convertLegacyBoard', () => {
  it('has nothing to do for a current URL', () => {
    expect(convertLegacyBoard(params('metric=wins&w=6m&as_of=2026-09-13'), CTX)).toBeNull();
  });

  it.each([
    ['period=season', { period: null, since: null, w: null }],
    ['period=ytd', { period: null, since: null, w: 'ytd' }],
    ['period=rolling_12', { period: null, since: null, w: '12m' }],
    ['period=all_time', { period: null, since: null, w: 'all' }],
    ['period=bogus', { period: null, since: null }],
    ['since=2026-06-01', { period: null, since: null }],
  ])('%s becomes a window', (query, updates) => {
    expect(convertLegacyBoard(params(query), CTX)).toEqual(updates);
  });

  it('turns a custom period into its dates, and the end date moves into the window', () => {
    expect(
      convertLegacyBoard(params('period=custom&since=2026-06-01&as_of=2026-09-13'), CTX),
    ).toEqual({ period: null, since: null, w: '2026-06-01..2026-09-13', as_of: null });
  });

  it('defaults a custom period to Jan 1 of the end year and to the latest Sunday', () => {
    expect(convertLegacyBoard(params('period=custom'), CTX)).toMatchObject({
      w: '2026-01-01..2026-09-27',
    });
    expect(convertLegacyBoard(params('period=custom&as_of=2025-06-01'), CTX)).toMatchObject({
      w: '2025-01-01..2025-06-01',
    });
  });

  it('waits for the latest Sunday when a custom end is missing, and drops a reversed range', () => {
    expect(convertLegacyBoard(params('period=custom'), { ...CTX, lastSunday: null })).toBe('wait');
    expect(
      convertLegacyBoard(params('period=custom&since=2026-09-27&as_of=2026-09-13'), CTX),
    ).toEqual({ period: null, since: null });
  });

  it('an explicit w wins, and the old keys still go', () => {
    expect(convertLegacyBoard(params('w=6m&period=ytd&since=2026-01-01'), CTX)).toEqual({
      period: null,
      since: null,
    });
  });

  it('converts the old rating metrics at the same time', () => {
    expect(convertLegacyBoard(params('metric=rating&period=ytd'), CTX)).toEqual({
      metric: 'rating_gain',
      period: null,
      since: null,
      w: 'ytd',
    });
    expect(convertLegacyBoard(params('metric=most_improved'), CTX)).toEqual({
      metric: 'rating_gain',
    });
  });

  it('writes no w when the window is the page default', () => {
    expect(convertLegacyBoard(params('period=rolling_12'), { ...CTX, pageDefault: '12m' })).toEqual(
      { period: null, since: null, w: null },
    );
  });
});

describe('convertLegacyRecords', () => {
  it('has nothing to do for a current URL', () => {
    expect(convertLegacyRecords(params('w=6m&rt=sporting'), CTX)).toBeNull();
  });

  it.each([
    ['rp=all', { rp: null, since: null, as_of: null, w: 'all' }],
    ['rp=ytd', { rp: null, since: null, as_of: null, w: 'ytd' }],
    ['rp=weird', { rp: null, since: null, as_of: null }],
    ['since=2024-01-07&as_of=2024-12-29', { rp: null, since: null, as_of: null }],
  ])('%s becomes a window', (query, updates) => {
    expect(convertLegacyRecords(params(query), CTX)).toEqual(updates);
  });

  it('turns a custom range into its dates, filling the first and latest Sunday', () => {
    expect(
      convertLegacyRecords(params('rp=custom&since=2024-01-07&as_of=2024-12-29'), CTX),
    ).toMatchObject({ w: '2024-01-07..2024-12-29' });
    expect(convertLegacyRecords(params('rp=custom'), CTX)).toMatchObject({
      w: '2020-01-05..2026-09-27',
    });
  });

  it('waits for /api/meta when a date is missing, and drops a reversed range', () => {
    expect(convertLegacyRecords(params('rp=custom'), { ...CTX, firstSunday: null })).toBe('wait');
    expect(
      convertLegacyRecords(params('rp=custom&since=2024-12-29&as_of=2024-01-07'), CTX),
    ).toEqual({ rp: null, since: null, as_of: null });
  });

  it('an explicit w wins', () => {
    expect(convertLegacyRecords(params('w=6m&rp=ytd'), CTX)).toEqual({
      rp: null,
      since: null,
      as_of: null,
    });
  });
});

describe('convertLegacyRace', () => {
  const race: LegacyContext = { ...CTX, pageDefault: '12m' };

  it('has nothing to do for a current URL, and keeps period (the points rule)', () => {
    expect(convertLegacyRace(params('period=ytd&metric=wins&w=6m'), race)).toBeNull();
  });

  it('turns since and until into a window', () => {
    expect(convertLegacyRace(params('since=2025-03-02&until=2025-06-29'), race)).toEqual({
      since: null,
      until: null,
      w: '2025-03-02..2025-06-29',
    });
    expect(convertLegacyRace(params('since=2025-03-02'), race)).toMatchObject({
      w: '2025-03-02..2026-09-27',
    });
  });

  it('drops an end date with no start, a reversed range, and waits for the latest Sunday', () => {
    expect(convertLegacyRace(params('until=2025-06-29'), race)).toEqual({
      since: null,
      until: null,
    });
    expect(convertLegacyRace(params('since=2025-06-29&until=2025-03-02'), race)).toEqual({
      since: null,
      until: null,
    });
    expect(convertLegacyRace(params('since=2025-03-02'), { ...race, lastSunday: null })).toBe(
      'wait',
    );
  });

  it('removes a stale period=custom, which is not a points rule', () => {
    expect(convertLegacyRace(params('period=custom&metric=wins'), race)).toEqual({ period: null });
    expect(convertLegacyRace(params('period=custom&since=2025-03-02'), race)).toMatchObject({
      period: null,
      w: '2025-03-02..2026-09-27',
    });
  });

  it('an explicit w wins, and the old rating metrics convert', () => {
    expect(convertLegacyRace(params('w=6m&since=2025-03-02'), race)).toEqual({
      since: null,
      until: null,
    });
    expect(convertLegacyRace(params('metric=most_improved'), race)).toEqual({
      metric: 'rating_gain',
    });
  });
});
