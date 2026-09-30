import { describe, expect, it } from 'vitest';
import { compareStations, stationRank } from './stationLabel';

describe('station labels', () => {
  it('orders a lettered station right after its number', () => {
    const labels = ['8', '7A', '10', '4', '7', '7B', '5'];
    expect([...labels].sort(compareStations)).toEqual(['4', '5', '7', '7A', '7B', '8', '10']);
  });

  it('ranks numbers and letters', () => {
    expect(stationRank('7')).toBe(700);
    expect(stationRank('7A')).toBe(701);
    expect(stationRank('12B')).toBe(1202);
  });

  it('puts anything that is not a label last, in text order', () => {
    expect(stationRank('x')).toBe(Number.MAX_SAFE_INTEGER);
    expect(['y', '3', 'x'].sort(compareStations)).toEqual(['3', 'x', 'y']);
  });
});
