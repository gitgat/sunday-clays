import { describe, expect, it } from 'vitest';
import { api } from '../../api/client';
import { eventSummaries } from './mocks';

const last = eventSummaries.map((e) => e.event_date).sort();

describe('the default /api/events handler', () => {
  it('answers a to-only request (the All window) with every Sunday up to that date', async () => {
    const { data } = await api.GET('/api/events', {
      params: { query: { to: last.at(-1) as string } },
    });
    expect(data).toHaveLength(eventSummaries.length);
  });

  it('bounds a from/to window inclusively and a year by its prefix', async () => {
    const first = last[0] as string;
    const one = await api.GET('/api/events', { params: { query: { from: first, to: first } } });
    expect(one.data?.map((e) => e.event_date)).toEqual([first]);
    const year = await api.GET('/api/events', { params: { query: { year: 1999 } } });
    expect(year.data).toEqual([]);
  });
});
