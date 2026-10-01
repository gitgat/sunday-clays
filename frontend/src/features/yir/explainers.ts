import type { Explainer } from '../../components/charts/types';

/**
 * Plain-language copy for the Year in Review cards and charts (.superpowers/sdd/explainers/STYLE.md;
 * checked against analytics/yir.py). A year means the calendar year, 1 January to 31 December.
 */
export const explainers = {
  glance: {
    what: 'The year in a few numbers, each set beside the year before so you can see how the club moved.',
    read: [
      'The number in brackets is this year minus last year. A plus means more than last year.',
    ],
    computed: [
      'Sundays with scores: Sundays in the year that have scores. Rounds: every 50-target round shot, second rounds included.',
      'Shooters: different people who shot at least one round. Newcomers: shooters whose very first round in our records fell in this year (people already shooting when the records begin are not counted).',
      'Clays broken: the sum of every round’s score. Average score: clays broken divided by rounds.',
    ],
  },
  highlights: {
    what: 'The standout moments of the year for the whole club.',
    computed: [
      'Top round: the highest score of the year, with everyone who shot it. Perfect 50s: rounds scoring 50.',
      'Busiest Sunday: the biggest head count (the earliest date if two tie), attendance-only Sundays included.',
      'Hardest and easiest Sunday: of the Sundays with complete results, the highest and lowest difficulty, the same figure as on the Sunday page. Difficulty is how many targets harder (plus) or easier (minus) the day played than a normal Sunday.',
      'Trophies earned: trophies awarded to anyone on a Sunday in the year.',
    ],
  },
  leaders: {
    what: 'Who topped the club’s standings this year.',
    read: ['Each list shows the top five. Tap a name to see their year.'],
    computed: [
      'The same numbers as the Leaderboards page, counting only Sundays from 1 January to 31 December (this year: to today).',
      'Average needs a few rounds to qualify, so a single lucky round cannot lead. Points: 1st to 8th place each Sunday earn 10, 8, 6, 5, 4, 3, 2 and 1, plus 1 for everyone who shot.',
    ],
  },
  clubMonths: {
    what: 'How busy and how well the club shot in each month of the year.',
    read: [
      'Bars are the rounds shot that month (left scale). The line is the average score (right scale).',
      'A month with no bar had no Sundays with scores.',
    ],
    computed: [
      'Rounds: every round shot on a Sunday in that month. Average: those rounds’ scores added up and divided by the number of rounds.',
    ],
  },
  shooterYear: {
    what: 'One shooter’s year in numbers.',
    read: [
      'A bracket such as “+3 vs 2024” means that much more than the year before. It only appears when the year was at least as good.',
    ],
    computed: [
      'Sundays: different days with a round. Rounds: 50-target rounds, second rounds included. Average: clays broken divided by rounds.',
      'Attendance: the place among everyone by Sundays shot in the year; shooters with the same number share a place.',
      'Rating gain: shown when the rating went up. It runs from the last rating before 1 January to the last rating in the year. The rating is our estimate of the score someone would post on a normal Sunday.',
    ],
  },
  shooterBest: {
    what: 'The high points of one shooter’s year.',
    computed: [
      'Best round: the highest score of the year (earliest date if repeated). Wins and podiums: each Sunday is ranked by everyone’s best round; 1st is a win (a tie for first counts for each), 1st to 3rd is a podium.',
      'Personal bests: rounds that beat all of that shooter’s earlier rounds, once at least five earlier rounds exist. Two rounds on one Sunday count as one day.',
      'Trophies earned: trophies awarded on a Sunday in the year.',
    ],
  },
  shooterMonths: {
    what: 'A shooter’s average score each month next to the whole club’s.',
    read: [
      'The club line shows how everyone shot that month, so you can see a good month even when the Sunday was tough.',
      'A gap in the shooter’s line is a month with no rounds.',
    ],
    computed: [
      'Each point is the scores of every round in that month added up and divided by the number of rounds, for the shooter and for the club.',
    ],
  },
} as const satisfies Record<string, Explainer>;
