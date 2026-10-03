import type { Explainer } from '../../components/charts/types';

/**
 * Plain-language copy per ChartFrame/ChartCard `urlKey` and per stat id
 * (.superpowers/sdd/explainers/STYLE.md, club-explorer.md). "Sunday with full results" = a Sunday
 * that has scores and where either no head count was written down or at least half the head
 * count have scores (domain/rebuild.py).
 */
export const explainers: Record<string, Explainer> = {
  // Club milestones (Plan 19)
  'club-milestone': {
    what: "The club's most recent round number, such as total clays thrown or Sundays held.",
    computed: [
      'We add up every Sunday on record since Jan 5, 2020, in date order, and note the Sunday each total first reached a round number.',
      'Special shoots count as a Sunday held and add their shooters, but not their clays or rounds.',
    ],
    scope: 'all-time',
    terms: ['held-sunday', 'special-shoot', 'clays-thrown'],
  },
  'club-milestones': {
    what: 'Every round number the club has passed, with the Sunday it was passed on.',
    computed: [
      'Totals add up every Sunday on record, in date order.',
      'A milestone is dated at the first Sunday its total reached the round number.',
      'Special shoots count as a Sunday held and add their shooters, but not their clays or rounds.',
    ],
    scope: 'all-time',
    terms: ['held-sunday', 'special-shoot', 'clays-thrown'],
  },
  ctot: {
    what: "How the club's running totals have grown, Sunday by Sunday, with each round number marked.",
    read: [
      'A dot marks the Sunday a round number was passed.',
      'A flat step on Clays thrown or Rounds is a special shoot: it counts as a Sunday held but adds no clays.',
    ],
    computed: [
      'Clays thrown: 50 for every regular round. Rounds: regular rounds only.',
      'Sundays held and Shooters include special shoots.',
      'Totals start at the first Sunday on record, Jan 5, 2020.',
    ],
    scope: 'windowed',
    terms: ['clays-thrown', 'special-shoot', 'held-sunday'],
  },
  // Charts
  att: {
    what: 'For every Sunday on record, how many people came (head count) next to how many rounds were scored.',
    read: [
      'Lines close together: nearly everyone who came has a score.',
      'Rounds above head count: doubleheaders. Rounds far below it, or at zero: scores are missing.',
      'A gap in the head-count line: no head count was written down.',
    ],
    computed: [
      'Head count is the number from the attendance sheet. Rounds is how many scored rounds we have.',
      'Every Sunday on record is listed, with or without scores.',
      'The round-type filter does not apply. The chart opens on the time window. Fullscreen shows every Sunday, and the CSV download has them all.',
    ],
    scope: 'windowed',
    terms: ['round-types', 'time-window'],
  },
  years: {
    what: 'For each year, how many different people shot and how many Sundays had full results.',
    read: [
      'The current year is still running, so its bars look short.',
      'In the table, year-to-date change compares this year so far with last year up to the same date.',
    ],
    computed: [
      'Shooters: different people with at least one round that year.',
      'Sundays: those with full results, up to today.',
      'Year-to-date change = (Sundays so far minus last year’s at the same date) ÷ last year’s. Every year is shown; the round-type filter does not apply.',
    ],
    scope: 'all-time',
    terms: ['held-sunday', 'round-types'],
  },
  season: {
    what: 'Which months of the year draw the biggest turnout, averaged over all years.',
    read: [
      'A taller bar means more people usually show up that month.',
      'No bar: no Sundays with full results in that month.',
      'Check “Sundays” in the table: a month built on 2 Sundays is a rough guess.',
    ],
    computed: [
      'Every Sunday with full results up to today, grouped by month (every January together).',
      'The average of their head counts; Sundays with no head count are skipped.',
      'The round-type filter does not apply.',
    ],
    scope: 'all-time',
    terms: ['held-sunday', 'round-types'],
  },
  turnout: {
    what: 'The average head count for each kind of weather.',
    read: [
      'A taller bar means a bigger turnout in that weather.',
      'Check “n” in the table (Sundays behind the bar): 2 is a guess.',
      'Rainy Sundays are also mostly winter Sundays, so this shows a pattern, not a cause.',
    ],
    computed: [
      'One number per Sunday: its head count. Sundays without one are skipped; Sundays with no scores count.',
      'Weather is 10 a.m. to noon: average temperature, strongest gust, total rain. Conditions, first match wins: rain (0.02 in or more), windy (gusts 20 mph or more), overcast (75% cloud or more), partly cloudy (30% or more), clear.',
      'On the page: only Sundays inside the time window. Fullscreen and the CSV download use every Sunday on record. The round-type filter applies: pick Super Sporting and every other Sunday drops out; Sundays with no station sheet count as Sporting.',
    ],
    scope: 'windowed',
    terms: ['round-types', 'time-window'],
  },
  dist: {
    what: 'How common each score was, one hill per year, newest on top.',
    read: [
      'Further right means higher scores. A tall, narrow hill means scores bunched together.',
      'Every hill is the same total size, so a quiet year looks as big as a busy one. See “Rounds” in the table.',
    ],
    computed: [
      'Every round that year (doubleheaders count twice) for the chosen round types, smoothed into a curve.',
      'Table: rounds, average, middle score, and the low end and high end (1 in 10 rounds score below or above them) and the lower and upper middle (1 in 4).',
      'Each year is its own hill, so the time window does not apply.',
    ],
    scope: 'all-time',
    terms: ['round-types'],
    // Says the time window does not apply here, so it is not offered as a word to look up.
    noTerms: ['time-window'],
  },
  scores: {
    what: 'How the field shot each Sunday: the middle score and the top score, each with a smoother trend line.',
    read: [
      'Middle score: half the rounds that Sunday were higher, half lower. Top score: the best single round.',
      'The 8-Sunday average smooths week-to-week noise. A rising line means scores are climbing.',
    ],
    computed: [
      'Sundays with full results, up to today. Every round counts, second rounds and both round types included.',
      '8-Sunday average = the average of that Sunday and the 7 before it (fewer at the start).',
      'The round-type filter does not apply. The chart opens on the time window. Fullscreen shows every Sunday, and the CSV download has them all.',
    ],
    scope: 'windowed',
    terms: ['held-sunday', 'round-types', 'time-window'],
  },
  diff: {
    what: 'How hard each Sunday was, in targets, against a typical Sunday of the past year.',
    read: [
      '+3 means the field shot about 3 targets below its usual level: a hard Sunday.',
      '−2 means about 2 targets above usual: an easy Sunday.',
      'The smooth line is the average of the last 8 Sundays.',
    ],
    computed: [
      'For each shooter: score that Sunday (averaged if they shot twice) minus their rating going in. Average those gaps across the field, pulled toward zero when few shot.',
      'Subtract the average gap of the past 364 days, then flip the sign so that plus means harder.',
      'Sundays with full results only. The round-type filter does not apply. The chart opens on the time window. Fullscreen shows every Sunday, and the CSV download has them all.',
    ],
    scope: 'windowed',
    terms: ['held-sunday', 'round-types', 'time-window'],
  },
  new: {
    what: 'How many people shot here for the first time each year, and how many of them ever came back.',
    read: [
      '“Came back” close to “Newcomers” means new people stick.',
      'Recent years look worse: their newcomers have had less time to return.',
    ],
    computed: [
      'A newcomer belongs to the year of their first-ever round.',
      '“Came back” = shot on at least two different Sundays, ever.',
      'People first seen in the first 8 weeks of records are left out (they may not be new). The round-type filter does not apply.',
    ],
    scope: 'all-time',
    terms: ['round-types'],
  },
  ret: {
    what: 'Of each year’s newcomers, the share who shot again the next year, and the year after.',
    read: [
      'A higher line means more newcomers keep coming.',
      'No point means that year has not happened yet.',
      'Small years swing a lot: 2 of 4 is 50%.',
    ],
    computed: [
      'People are grouped by the year of their first round (first 8 weeks of records left out).',
      'Next year: the share with a round in the next calendar year. Year after: a round two calendar years later, even if they skipped the year between.',
      'The round-type filter does not apply.',
    ],
    scope: 'all-time',
    terms: ['round-types'],
  },
  status: {
    what: 'Each year’s rounds split by the status written on the score sheet: member, guest, in memoriam or not recorded.',
    read: [
      'A bigger member share means mostly regulars.',
      'A growing guest share means more visitors.',
    ],
    computed: [
      'Rounds are counted, not people, by the status written on that round’s row.',
      'A member who shoots twice on one Sunday adds two member rounds.',
      'Rounds with no recognised status go to “Status not recorded”. The round-type filter applies.',
    ],
    scope: 'all-time',
    terms: ['round-types'],
  },
  conv: {
    what: 'Of the guests first seen each year, how many later shot as members.',
    read: [
      'Each year is one group of first-time guests. The second bar is how many of that group have joined so far.',
      'Recent years read low: those guests have had less time to join.',
      '“Median days to join” is the typical wait from first guest round to first member round.',
    ],
    computed: [
      'A guest counts in the year of their first round marked guest.',
      'They joined if they have a later round marked member. Joiners stay in their guest year’s group.',
      '% who joined = joined ÷ first-time guests, same year. The round-type filter does not apply.',
    ],
    scope: 'all-time',
    terms: ['round-types'],
  },
  parity: {
    what: 'How open the competition is: do the same few people win, and does the favorite?',
    read: [
      'Top-3 share: lower means wins spread across more people.',
      'Favorite’s win rate: lower means more surprises.',
      'A year with few Sundays shows a high top-3 share.',
    ],
    computed: [
      'The winner is the top score that Sunday (best rounds only); ties all win. Every scored Sunday counts.',
      'Top-3 share = wins by the year’s 3 biggest winners ÷ all wins.',
      'Favorite = highest rating going in; Sundays with a tie for top rating are skipped. The round-type filter does not apply.',
    ],
    scope: 'all-time',
    terms: ['round-types'],
  },

  // Header stats
  'stat-sundays': {
    what: 'How many Sundays in the time window have full results.',
    read: [
      'Sundays with only a head count, or with scores for fewer than half the people who came, are not counted.',
    ],
    computed: [
      'Every Sunday with full results between the window’s first and last date (the tag above the numbers).',
      'The round-type filter applies: pick Sporting and only sporting Sundays count.',
    ],
    scope: 'windowed',
    terms: ['held-sunday', 'round-types', 'time-window'],
  },
  'stat-shooters': {
    what: 'How many different people shot a scored round in the time window.',
    read: [
      'Each person counts once, however often they came. Members, guests and in-memoriam shooters all count.',
      'A guest recorded by first name only counts as a new person each Sunday, so this can run high.',
    ],
    computed: [
      'Different shooters with at least one round on a Sunday inside the window.',
      'The round-type filter applies: someone who only shot super sporting drops out when you pick Sporting.',
    ],
    scope: 'windowed',
    terms: ['round-types', 'time-window'],
  },
  'stat-rounds': {
    what: 'Rounds of 50 targets shot in the time window.',
    read: ['A shooter who shoots twice on a doubleheader Sunday adds two rounds.'],
    computed: [
      'Every scored round on a Sunday inside the window.',
      'The round-type filter applies.',
    ],
    scope: 'windowed',
    terms: ['round-types', 'time-window'],
  },
  'stat-clays': {
    what: 'Targets broken by everyone in the time window.',
    read: ['It is every score added together: a 38 out of 50 adds 38.'],
    computed: [
      'The sum of every round’s score on a Sunday inside the window.',
      'The round-type filter applies.',
    ],
    scope: 'windowed',
    terms: ['round-types', 'time-window'],
  },
  'stat-first': {
    what: 'The first Sunday inside the time window that we have scores for.',
    read: ['With the All window this is the earliest Sunday we have scores for.'],
    computed: [
      'The earliest Sunday in the window with at least one score.',
      'The round-type filter applies, so this date can move when you pick a round type.',
    ],
    scope: 'windowed',
    terms: ['round-types', 'time-window'],
  },

  // Regulars lists
  'regulars-core': {
    what: 'People who shoot at least half of our Sundays.',
    read: [
      '“14 of 26 Sundays” means they shot on 14 of the 26 Sundays with full results in the past year. Most Sundays first.',
    ],
    computed: [
      'Take the Sundays with full results in the 364 days up to the latest Sunday with scores. The time window does not change this.',
      'A core regular has a score on at least half of them. Two rounds on one Sunday count once.',
      'In-memoriam shooters are left out. The round-type filter does not apply.',
    ],
    terms: ['held-sunday', 'round-types', 'time-window'],
  },
  'regulars-lapsed': {
    what: 'People who used to shoot most Sundays but have not been out lately.',
    read: ['“Last out Mar 3, 2026” is the Sunday of their most recent round. Longest gone first.'],
    computed: [
      '180 days ago they were core regulars: a score on at least half the Sundays with full results in the 364 days before that.',
      'They have no round in the 90 days up to the latest Sunday with scores. The time window does not change this.',
      'In-memoriam shooters are left out. The round-type filter does not apply.',
    ],
    terms: ['held-sunday', 'round-types', 'time-window'],
  },
  'first-rounds': {
    what: 'How shooters did on their first Sunday at the club: how many opened with each score.',
    read: [
      'Taller bars are the scores most people start with.',
      'A ringed bar is the score an insight points to.',
    ],
    computed: [
      'First round = the best round on the first Sunday a shooter appears on the score sheets.',
      'Only shooters whose first Sunday falls inside the time window are counted, each once, out of 50. Pick All to include everyone.',
      'The round-type filter does not apply.',
    ],
    scope: 'windowed',
    terms: ['round-types', 'time-window'],
  },
};
