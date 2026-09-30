import { describe, expect, it } from 'vitest';
import { buildRulePayload, EMPTY_FIELDS, RULE_LABELS, RULE_TYPES, ruleSummary } from './rules';
import type { RuleFields, RuleType } from './rules';

const hadley = { shooter_id: 3, display_name: 'Hadley, Ike' };
const al = { shooter_id: 90, display_name: 'Crimson, Al' };
const round = {
  event_date: '2026-09-13',
  name_key: 'hadley ike',
  ordinal: 1,
  display_name: 'Hadley, Ike',
  score: 34,
};
const f = (over: Partial<RuleFields>): RuleFields => ({ ...EMPTY_FIELDS, ...over });

describe('RULE_TYPES', () => {
  it('offers exactly the eight C5 rule types, each with a label', () => {
    expect([...RULE_TYPES].sort()).toEqual([
      'alias_name',
      'hide_round',
      'merge_shooter',
      'rename_shooter',
      'round_type_override',
      'score_override',
      'set_status',
      'station_reset',
    ]);
    expect(RULE_TYPES.every((t) => RULE_LABELS[t].length > 0)).toBe(true);
  });
});

describe('buildRulePayload', () => {
  it.each<[RuleType, Partial<RuleFields>, Record<string, string | number>]>([
    [
      'merge_shooter',
      { source: al, target: hadley },
      { source_shooter_id: 90, target_shooter_id: 3 },
    ],
    [
      'rename_shooter',
      { shooter: hadley, displayName: '  Hadley, Clint ' },
      { shooter_id: 3, display_name: 'Hadley, Clint' },
    ],
    [
      'score_override',
      { round, score: '36' },
      { event_date: '2026-09-13', name_key: 'hadley ike', ordinal: 1, score: 36 },
    ],
    ['hide_round', { round }, { event_date: '2026-09-13', name_key: 'hadley ike', ordinal: 1 }],
    [
      'round_type_override',
      { eventDate: '2026-09-13', roundType: 'super_sporting' },
      { event_date: '2026-09-13', round_type: 'super_sporting' },
    ],
    ['set_status', { shooter: hadley, status: 'deceased' }, { shooter_id: 3, status: 'deceased' }],
    [
      'station_reset',
      { stationNo: '6', effectiveDate: '2026-10-04', resetNote: ' New presentation ' },
      { station: '6', effective_date: '2026-10-04', note: 'New presentation' },
    ],
    [
      'station_reset',
      { stationNo: ' 7a ', effectiveDate: '2026-10-04', resetNote: 'x' },
      { station: '7A', effective_date: '2026-10-04', note: 'x' },
    ],
    [
      'station_reset',
      { stationNo: '07B', effectiveDate: '2026-10-04', resetNote: 'x' },
      { station: '7B', effective_date: '2026-10-04', note: 'x' },
    ],
    [
      'alias_name',
      { nameKey: ' hadley dik ', shooter: hadley },
      { name_key: 'hadley dik', shooter_id: 3 },
    ],
  ])('%s builds its C5 payload', (type, fields, want) => {
    expect(buildRulePayload(type, f(fields))).toEqual(want);
  });

  it.each<[RuleType, Partial<RuleFields>]>([
    ['merge_shooter', { source: hadley }],
    ['merge_shooter', { source: hadley, target: hadley }],
    ['rename_shooter', { shooter: hadley, displayName: '   ' }],
    ['rename_shooter', { displayName: 'Hadley, Clint' }],
    ['score_override', { round, score: '' }],
    ['score_override', { round, score: '51' }],
    ['score_override', { round, score: '36.5' }],
    ['score_override', { score: '36' }],
    ['hide_round', {}],
    ['round_type_override', { eventDate: '2026-09-13' }],
    ['round_type_override', { roundType: 'sporting' }],
    ['set_status', { shooter: hadley }],
    ['set_status', { status: 'guest' }],
    ['station_reset', { stationNo: '0', effectiveDate: '2026-10-04', resetNote: 'x' }],
    ['station_reset', { stationNo: '00', effectiveDate: '2026-10-04', resetNote: 'x' }],
    ['station_reset', { stationNo: '7AB', effectiveDate: '2026-10-04', resetNote: 'x' }],
    ['station_reset', { stationNo: 'A7', effectiveDate: '2026-10-04', resetNote: 'x' }],
    ['station_reset', { stationNo: '123', effectiveDate: '2026-10-04', resetNote: 'x' }],
    ['station_reset', { stationNo: '6.5', effectiveDate: '2026-10-04', resetNote: 'x' }],
    ['station_reset', { stationNo: '', effectiveDate: '2026-10-04', resetNote: 'x' }],
    ['station_reset', { stationNo: '6', resetNote: 'x' }],
    ['station_reset', { stationNo: '6', effectiveDate: '2026-10-04', resetNote: ' ' }],
    ['alias_name', { nameKey: 'hadley dik' }],
    ['alias_name', { shooter: hadley }],
  ])('%s is incomplete for %j', (type, fields) => {
    expect(buildRulePayload(type, f(fields))).toBeNull();
  });
});

describe('ruleSummary', () => {
  it('lists the payload as key=value pairs', () => {
    expect(
      ruleSummary({
        event_date: '2026-09-13',
        name_key: 'hadley ike',
        ordinal: 1,
        raw_score: 34,
        score: 36,
      }),
    ).toBe('event_date=2026-09-13, name_key=hadley ike, ordinal=1, raw_score=34, score=36');
  });
});
