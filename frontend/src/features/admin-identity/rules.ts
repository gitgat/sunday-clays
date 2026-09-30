import type { ShooterOption } from '../admin/api';

/** The eight C5 RuleType values, in form order. */
export const RULE_TYPES = [
  'merge_shooter',
  'rename_shooter',
  'score_override',
  'hide_round',
  'round_type_override',
  'set_status',
  'station_reset',
  'alias_name',
] as const;
export type RuleType = (typeof RULE_TYPES)[number];

export const RULE_LABELS: Record<RuleType, string> = {
  merge_shooter: 'Merge two shooters',
  rename_shooter: 'Rename a shooter',
  score_override: 'Override a score',
  hide_round: 'Hide a round',
  round_type_override: 'Set an event’s round type',
  set_status: 'Set a shooter’s status',
  station_reset: 'Log a station reset',
  alias_name: 'Alias a name to a shooter',
};

export type RoundRef = {
  event_date: string;
  name_key: string;
  ordinal: number;
  display_name: string;
  score: number;
};

export type RuleFields = {
  source: ShooterOption | null;
  target: ShooterOption | null;
  shooter: ShooterOption | null;
  displayName: string;
  round: RoundRef | null;
  score: string;
  eventDate: string;
  roundType: string;
  status: string;
  stationNo: string;
  effectiveDate: string;
  resetNote: string;
  nameKey: string;
};

export const EMPTY_FIELDS: RuleFields = {
  source: null,
  target: null,
  shooter: null,
  displayName: '',
  round: null,
  score: '',
  eventDate: '',
  roundType: '',
  status: '',
  stationNo: '',
  effectiveDate: '',
  resetNote: '',
  nameKey: '',
};

const roundTarget = (r: RoundRef) => ({
  event_date: r.event_date,
  name_key: r.name_key,
  ordinal: r.ordinal,
});

const STATION_LABEL = /^(\d{1,2})([A-Z]?)$/;

/** "7", "7a" or " 07A " as the label the backend reads ("7", "7A"); null for anything else or 0. */
export function stationLabel(input: string): string | null {
  const match = STATION_LABEL.exec(input.trim().toUpperCase());
  if (match === null) return null;
  const number = Number(match[1]);
  return number >= 1 ? `${String(number)}${match[2] as string}` : null;
}

/** The C5 payload for `type`, or null while a required field is missing or invalid. */
export function buildRulePayload(
  type: RuleType,
  f: RuleFields,
): Record<string, string | number> | null {
  switch (type) {
    case 'merge_shooter':
      return f.source !== null && f.target !== null && f.source.shooter_id !== f.target.shooter_id
        ? { source_shooter_id: f.source.shooter_id, target_shooter_id: f.target.shooter_id }
        : null;
    case 'rename_shooter':
      return f.shooter !== null && f.displayName.trim() !== ''
        ? { shooter_id: f.shooter.shooter_id, display_name: f.displayName.trim() }
        : null;
    case 'score_override': {
      const score = Number(f.score);
      return f.round !== null &&
        f.score !== '' &&
        Number.isInteger(score) &&
        score >= 0 &&
        score <= 50
        ? { ...roundTarget(f.round), score }
        : null;
    }
    case 'hide_round':
      return f.round === null ? null : roundTarget(f.round);
    case 'round_type_override':
      return f.eventDate !== '' && f.roundType !== ''
        ? { event_date: f.eventDate, round_type: f.roundType }
        : null;
    case 'set_status':
      return f.shooter !== null && f.status !== ''
        ? { shooter_id: f.shooter.shooter_id, status: f.status }
        : null;
    case 'station_reset': {
      const station = stationLabel(f.stationNo);
      return station !== null && f.effectiveDate !== '' && f.resetNote.trim() !== ''
        ? { station, effective_date: f.effectiveDate, note: f.resetNote.trim() }
        : null;
    }
    case 'alias_name':
      return f.nameKey.trim() !== '' && f.shooter !== null
        ? { name_key: f.nameKey.trim(), shooter_id: f.shooter.shooter_id }
        : null;
  }
}

export function ruleSummary(payload: Record<string, unknown>): string {
  return Object.entries(payload)
    .map(([key, value]) => `${key}=${String(value)}`)
    .join(', ');
}
