import { describe, expect, it } from 'vitest';
import { explainers as achievements } from '../../features/achievements/explainers';
import { explainers as club } from '../../features/club/explainers';
import { eventExplainers } from '../../features/events/explainers';
import { homeExplainers } from '../../features/home/explainers';
import { explainers as predictions } from '../../features/predictions/explainers';
import { explainers as shooters } from '../../features/shooters/explainers';
import { explainers as stations } from '../../features/stations/explainers';
import { explainers as summary } from '../../features/summary/explainers';
import { explainers as weather } from '../../features/weather/explainers';
import { explainers as yir } from '../../features/yir/explainers';
import {
  THROWN_OUT_COUNTS,
  THROWN_OUT_HOLLOW,
  THROWN_OUT_ROUNDS,
  THROWN_OUT_STATION,
} from './thrownOutCopy';
import type { Explainer } from './types';

type Book = Record<string, Explainer>;
const text = (book: Book, key: string) => {
  const e = book[key];
  return [e?.what ?? '', ...(e?.read ?? []), ...(e?.computed ?? [])].join(' ');
};
const R = THROWN_OUT_ROUNDS,
  C = THROWN_OUT_COUNTS,
  H = THROWN_OUT_HOLLOW;
const CASES: [string, Book, string, string[]][] = [
  ['events', eventExplainers, R, ['difficulty', 'vsPrev']],
  ['events', eventExplainers, C, ['calendar', 'results', 'median', 'topScore']],
  ['home', homeExplainers, R, ['pulseHigh']],
  ['home', homeExplainers, C, ['latestMedian', 'latestTop', 'meLast', 'meOdometer']],
  ['stations', stations, THROWN_OUT_STATION, Object.keys(stations)],
  [
    'shooters',
    shooters,
    R,
    [
      'rating',
      'trend',
      'dist',
      'learn',
      'splits',
      'tough-days',
      'hero-average',
      'hero-median',
      'hero-best',
      'win-average',
      'win-best',
      'odometer',
      'floor-ceiling',
      'bad-day',
      'form',
      'peak',
      'rust',
      'pbs',
    ],
  ],
  [
    'shooters',
    shooters,
    C,
    ['finishes', 'cal', 'hero-rounds', 'win-rounds', 'odometer', 'wins', 'field-beaten'],
  ],
  ['shooters', shooters, H, ['trend', 'finishes']],
  ['club', club, R, ['dist', 'scores', 'diff', 'first-rounds']],
  ['club', club, C, ['stat-clays', 'parity']],
  ['club', club, H, ['scores']],
  ['weather', weather, R, ['wf', 'wr', 'wb', 'ws', 'conditions', 'profile-sensitivity']],
  [
    'yir',
    yir,
    R,
    [
      'glance',
      'highlights',
      'leaders',
      'clubMonths',
      'shooterYear',
      'shooterBest',
      'shooterMonths',
    ],
  ],
  ['yir', yir, C, ['glance', 'leaders', 'shooterYear', 'onThisDay']],
  ['predictions', predictions, R, ['next-sunday']],
  ['achievements', achievements, R, ['trophy-progress', 'next-trophy']],
  ['achievements', achievements, C, ['trophy-progress']],
  ['summary', summary, R, ['summary-card']],
  ['summary', summary, C, ['summary-card']],
];

describe('thrown-out disclosure', () => {
  it('pins the shared lines', () => {
    expect(THROWN_OUT_ROUNDS).toBe('Sundays with a station thrown out (marked *) are left out.');
    expect(THROWN_OUT_STATION).toBe('A station thrown out on the day is left out.');
    expect(THROWN_OUT_COUNTS).toBe('Sundays with a station thrown out count here, marked *.');
    expect(THROWN_OUT_HOLLOW).toBe('A hollow point is a Sunday with a station thrown out.');
  });
  it.each(CASES)(
    '%s: every listed explainer says the line and lists the term',
    (_f, book, line, keys) => {
      for (const key of keys) {
        expect(text(book, key), key).toContain(line);
        expect(book[key]?.terms, key).toContain('thrown-out-station');
      }
    },
  );
  it('leaves turnout and count-only explainers alone', () => {
    for (const key of ['shooters', 'headCount', 'stations', 'weather', 'special', 'notables'])
      expect(text(eventExplainers, key), key).not.toMatch(/thrown out/);
    for (const key of ['pulse', 'pulseHeld', 'pulseTurnout', 'latestShooters'])
      expect(text(homeExplainers, key), key).not.toMatch(/thrown out/);
    expect(text(weather, 'wt')).not.toMatch(/thrown out/);
  });
  it('no longer defines an average as clays broken divided by rounds', () => {
    for (const [book, key] of [
      [yir, 'glance'],
      [yir, 'shooterYear'],
      [shooters, 'odometer'],
      [club, 'stat-clays'],
    ] as const)
      expect(text(book, key), key).not.toMatch(/clays broken divided by rounds/i);
    expect(yir.glance.computed).toContain(
      `Average score: the scores added up and divided by the rounds they come from. ${R}`,
    );
    expect(yir.shooterYear.computed).toContain(
      `Average: the scores added up and divided by the rounds they come from. ${R}`,
    );
    expect(shooters.odometer.computed).toContain(`Hit rate = broken ÷ thrown. ${R}`);
    expect(shooters.odometer.computed).toContain(
      `Clays thrown = rounds × 50. Clays broken = all your scores added up. ${C}`,
    );
  });
  it('says the thrown-out heatmap column is greyed and credited', () =>
    expect(eventExplainers.stn.read).toContain(
      'A station thrown out that day is greyed, marked * and reads "credited".',
    ));
});
