import type { Explainer } from '../../components/charts/types';

const SHEETS_ONLY = 'Only Sundays with a station sheet count (older station sheets were not kept).';
const WINDOW =
  'Only Sundays inside the time window you picked count; the line under the page title names the dates.';
const LETTERED =
  'A lettered station such as 7A is its own station: it is counted apart from 7 and listed right after it.';

/**
 * Plain-language copy per ChartFrame `urlKey` or table id (.superpowers/sdd/explainers/STYLE.md).
 * Checked against backend analytics/stations.py: every number comes from the station sheets (hits
 * written down per station), never from a round's final score, and every round counts.
 */
export const explainers: Record<string, Explainer> = {
  'station-summary': {
    what: 'One line per station: how often its targets break, how often it is shot clean, and whether it sorts strong shooters from the rest.',
    read: [
      'Lower Hit % means a harder station.',
      'Clean rate is how often every target at that station was broken.',
      'Separator runs from −1 to 1. Near 0, everyone does about the same there; nearer 1, strong shooters pull ahead.',
    ],
    computed: [
      'Hit % = targets broken ÷ targets thrown at that station, every shooter and round. Likely range: see Hit % by station.',
      'Clean rate = rounds with every target broken here ÷ all rounds here.',
      'Separator compares each shooter’s result here with the rest of their sheet that Sunday. It needs 30 or more rounds, otherwise a dash.',
      LETTERED,
      WINDOW,
      SHEETS_ONLY,
    ],
  },
  sthit: {
    what: 'The share of targets broken at each station, with a tick above and below each bar showing a likely range.',
    read: [
      'A shorter bar means a harder station.',
      'When two stations’ ranges overlap, the gap between them may just be luck.',
      'A wide range means little data or big swings between Sundays.',
    ],
    computed: [
      'Bar = targets broken ÷ targets thrown at that station, all shooters, every round. The setup choice decides which setups count.',
      'Likely range = where the true hit % probably sits (19 times in 20), widened when whole Sundays run hot or cold together.',
      'Not adjusted for who shot.',
      LETTERED,
      WINDOW,
      SHEETS_ONLY,
    ],
  },
  sttime: {
    what: 'One line per station: the share of its targets broken on each Sunday.',
    read: [
      'A dip means the station played harder that Sunday.',
      'Many lines dipping together means a hard day (wind, light), not one bad station.',
      'A step after a reset shows the change mattered.',
    ],
    computed: [
      'For each Sunday and station: targets broken by everyone ÷ targets thrown. Every round counts, and a 3-shooter Sunday counts like a 30-shooter one.',
      '“Since last reset” shows each station only since its latest reset. The chart and its table cover the time window you picked. Fullscreen shows every Sunday, and the CSV download has them all.',
      WINDOW,
      SHEETS_ONLY,
    ],
    scope: 'windowed',
  },
  stmatrix: {
    what: 'A grid: each row is a shooter, each column a station, and each square is that shooter’s hit % at that station.',
    read: [
      'Across a row: strong and weak stations. Down a column: who does best at one station.',
      'Colour is fixed for every square: red at 50% or lower, shading to peach at 100%. Peach means more targets broken.',
      'Hover a square to see how many rounds are behind it.',
    ],
    computed: [
      'Square = the shooter’s targets broken ÷ targets thrown at that station (setup choice and round-type filter apply).',
      'A shooter needs at least 3 rounds at a station to get a square; with fewer the table says “not enough rounds yet”.',
      'Only shooters matched to a profile appear.',
      WINDOW,
      SHEETS_ONLY,
    ],
  },
  stera: {
    what: 'How this station has played in each of its setups, split on the dates it was reset or rebuilt.',
    read: [
      'Bars are labelled “Original setup” or “Since <date>”.',
      'A taller bar after a reset means the change made it easier; shorter means harder.',
    ],
    computed: [
      'For each setup: targets broken ÷ targets thrown at this station, every shooter and round in that stretch. The round-type filter applies.',
      'A setup starts on its reset date (that Sunday counts in the new setup). A setup with no sheets yet gets no bar.',
      'This chart always shows every setup the station had inside the time window; the setup choice does not change it.',
      WINDOW,
      SHEETS_ONLY,
    ],
  },
  stwind: {
    what: 'How this station plays on calm, breezy and gusty days.',
    read: [
      'Bars: hit % on Sundays with gusts under 10 mph, 10 up to 20 mph, and 20 mph or more.',
      'Bars that fall as gusts rise mean wind hurts this station.',
      'A grey “too few” bar rests on fewer than 5 Sundays: treat it as a hint.',
    ],
    computed: [
      'A Sunday’s gust = the strongest gust recorded between 10am and noon.',
      'Per band: targets broken ÷ targets thrown here on those Sundays, every round. The setup choice and round-type filter apply.',
      'Sundays without weather are left out.',
      WINDOW,
      SHEETS_ONLY,
    ],
  },
  'station-leaders': {
    what: 'The shooters who break the highest share of this station’s targets. The first ten show; “Show all” lists the rest.',
    read: [
      'Best first. “72.00% · 8 rounds” is their share of targets broken here and how many rounds that is based on.',
    ],
    computed: [
      'Per shooter: targets broken ÷ targets thrown at this station over their rounds. The setup choice and round-type filter apply.',
      'A shooter needs at least 3 rounds at the station to be listed. Ties go to whoever has thrown more targets there.',
      'Two rounds on one Sunday count as 2 rounds. Only shooters matched to a profile appear.',
      WINDOW,
      SHEETS_ONLY,
    ],
  },
  stdelta: {
    what: 'How many percentage points better or worse than the field you shoot each station.',
    read: [
      'Below zero (red) means you drop more targets than the field; above zero (peach) means you beat it.',
      'About −5 points is roughly one extra miss per 20 targets.',
    ],
    computed: [
      'Field = everyone’s hit % at that station on the Sundays you shot it (you included).',
      'Your hit % is pulled toward the field’s, as if you had shot two extra average rounds there, so one fluke round cannot swing it. Then the field’s % is subtracted.',
      'A station needs 2 or more of your rounds to show. The setup choice and round-type filter apply.',
      'The CSV download lists every station; a station shot fewer than twice has no versus-field number.',
      WINDOW,
      SHEETS_ONLY,
    ],
  },
  'stdelta-table': {
    what: 'Every station you have shot: your hit %, the field’s hit % on the same Sundays, the gap and how many rounds it rests on.',
    read: [
      'Versus field: + means better than the field, − means worse. A dash means only one round there so far.',
    ],
    computed: [
      'Hit % = your targets broken ÷ thrown at that station, every round. Field = everyone’s (you included) on the Sundays you shot it.',
      'Versus field is pulled toward zero for small samples (see the chart above), so it will not exactly equal Hit % minus Field.',
      'The setup choice and round-type filter apply.',
      WINDOW,
      SHEETS_ONLY,
    ],
  },
};
