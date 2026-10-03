import type { Explainer } from '../../components/charts/types';

/**
 * Plain-language copy per ChartFrame `urlKey` and per profile stat id
 * (.superpowers/sdd/explainers/STYLE.md).
 */
export const explainers = {
  rating: {
    what: 'Our estimate of your skill over time, in targets out of 50 on a typical Sunday, with a shaded likely range.',
    read: [
      'A rising line means you are improving. The pin marks your highest rating.',
      'Narrow shading means we are fairly sure. It is wide when you are new and widens after time away.',
    ],
    computed: [
      'Everyone starts at 30. After each Sunday with complete results the rating moves part way toward your score that day, allowing for how hard the day was for everyone else.',
      'Likely range: we are about 95% sure your true level sits inside it.',
      'Opens on the time window. Fullscreen opens on all your history, and the CSV download has every point. Ignores the round-type filter.',
    ],
    scope: 'windowed',
    terms: ['time-window'],
  },
  trend: {
    what: 'Every round you shot: your score, and your score against the field that Sunday. Pins mark new personal bests.',
    read: [
      'Above 0 on the right-hand scale means you beat that Sunday’s middle score; below 0 means you trailed it.',
      'A score that drops while the right-hand line holds steady means the targets were just harder.',
    ],
    computed: [
      'Vs middle score = your score minus the middle score of every round shot that Sunday. Blank when the Sunday’s results are incomplete.',
      'A PB pin marks a round that beat all your earlier rounds, once you have 5 or more earlier rounds. Ties do not count.',
      'Line chooser: the 10- or 20-Sunday average is the average of your best round on each of your last 10 or 20 Sundays; average so far is every round you shot before that Sunday; personal best is your highest round up to that Sunday.',
      'One point per round, spaced evenly. Opens on the time window. Fullscreen shows every round you have shot, and the CSV download has them all. The round-type filter applies.',
    ],
    scope: 'windowed',
    terms: ['personal-best', 'time-window'],
  },
  finishes: {
    what: 'Where you finished on each Sunday with full results, 1st at the top.',
    read: ['Points on or above the dashed line are podium finishes (1st to 3rd).'],
    computed: [
      'Place = your best round that Sunday against everyone else’s best round; ties share the place.',
      'Only Sundays with complete results count. Opens on the time window. Fullscreen shows every Sunday you finished, and the CSV download has them all. The round-type filter applies.',
    ],
    scope: 'windowed',
    terms: ['held-sunday', 'time-window'],
  },
  dist: {
    what: 'How often you shoot each score in the time window, next to how often the whole club does in the same window.',
    read: [
      'Your bars sitting further right than the club’s means you usually outscore the field.',
      'A tall, narrow cluster means you are consistent week to week.',
    ],
    computed: [
      'For each score from the lowest anyone has shot up to 50: the share of your rounds that were exactly that score, and the same share across every club round (yours included). Both sides only count Sundays inside the time window.',
      'Every round counts, including second rounds and Sundays with incomplete results.',
      'The round-type filter applies to both sides. Fullscreen and the CSV download show every round and every year.',
    ],
    scope: 'windowed',
    terms: ['time-window'],
  },
  learn: {
    what: 'How you improved with experience, next to a typical club shooter at the same stage.',
    read: [
      'Above the club line means you were ahead of most shooters after the same number of Sundays.',
      '0 matches that Sunday’s middle score. Rising means you are gaining on the field.',
    ],
    computed: [
      'Your Sundays with complete results are numbered 1, 2, 3 and so on. Each point is your score minus that Sunday’s middle score (two rounds averaged).',
      'Club line = the middle of every shooter’s value at their own 1st, 2nd, 3rd Sunday, leaving out shooters who were already regulars when records began. It shows only once at least 3 shooters have reached that Sunday.',
      'Career-long, so the time window and the round-type filter are ignored.',
    ],
    scope: 'all-time',
    terms: ['time-window'],
  },
  splits: {
    what: 'Your average score in the time window by year, time of year (winter to fall), month, round type, gauge or weather, so you can see where you shoot best.',
    read: [
      'A taller bar means a higher average. Check the round count in the table: a bar from 2 rounds means little.',
      'These are raw scores, not adjusted for how hard the day was.',
    ],
    computed: [
      'Average = your scores in the group divided by the rounds in it. Every round inside the time window counts; the round-type filter applies.',
      'Winter is Dec to Feb, and so on. Month means each month of each year separately.',
      'Weather uses 10 am to noon that day: average temperature (°F), strongest gust (mph) and total rain (0.02 in or more counts as wet).',
      'Fullscreen and the CSV download cover every round you have shot.',
    ],
    scope: 'windowed',
    terms: ['field-adjusted', 'round-types', 'time-window'],
  },
  cal: {
    what: 'Every Sunday the club shot this year. Filled squares are Sundays you shot; outlined ones you missed.',
    read: [
      'A filled square shows your best round that day, out of 50; brighter means a higher score.',
      'Click a filled square to open that Sunday.',
      'A ★ square is a special shoot you came to. It counts as a Sunday shot and has no colour, because its score is out of a different total.',
    ],
    computed: [
      'Best score = your highest single round that Sunday.',
      'Missed = the club has complete results for that Sunday and you have no round in it. A special shoot is never missed.',
      'The round-type filter applies to your rounds and to the club’s Sundays, special shoots included. The calendar opens on the year the time window ends in; the year tabs pick any other year.',
      'The fullscreen table and the CSV download cover every year you shot.',
    ],
    scope: 'all-time',
    terms: ['special-shoot', 'time-window'],
  },
  'cal-month': {
    what: 'How many Sundays you shot in each month, from your first round to your latest.',
    read: [
      'A gap in the bars is a month you did not shoot, and a tall bar is a month you were out most Sundays.',
      'Ringed bars are the months an insight points to.',
    ],
    computed: [
      'Each Sunday counts once, however many rounds you shot that day, special shoots included. The round-type filter applies.',
      'Opens on the year the time window ends in; fullscreen and the CSV download show every month.',
    ],
    scope: 'windowed',
    terms: ['special-shoot', 'time-window'],
  },
  'tough-days': {
    what: 'Every Sunday you shot, placed by how hard the day played for the whole field and by how you did against that field.',
    read: [
      'Further right means a harder day for everyone. Higher means you beat the day’s middle score by more.',
      'Points up and to the right are hard days where you came out ahead of the field.',
      'Ringed points are the Sundays an insight points to. Click a row in the table to open that Sunday.',
    ],
    computed: [
      'How the day played = how much harder that Sunday was than a typical Sunday of the past year, in targets, allowing for who shot (positive = harder, negative = easier).',
      'Against the field = your best round that Sunday minus the middle score of every round shot that day. Only Sundays with complete results appear.',
      'Opens on the time window; fullscreen and the CSV download show every Sunday you shot. The round-type filter picks which of your Sundays appear; how hard the day played always uses everyone’s scores that Sunday.',
    ],
    scope: 'windowed',
    terms: ['time-window'],
  },
  'hero-rounds': {
    what: 'How many rounds you have shot, for the round types picked in the filter.',
    computed: [
      'Every round counts, including second rounds on the same day and Sundays with incomplete results.',
    ],
    scope: 'all-time',
    terms: ['round-types'],
  },
  'hero-sundays': {
    what: 'How many different Sundays you have shot, for the round types picked in the filter.',
    computed: [
      'A day counts once however many rounds you shot. Sundays with incomplete results count.',
    ],
    scope: 'all-time',
    terms: ['round-types'],
  },
  'hero-average': {
    what: 'Your typical score out of 50.',
    read: ['An average well below your median means a few bad rounds are pulling it down.'],
    computed: [
      'All your scores added up, divided by your rounds.',
      'The round-type filter applies.',
    ],
    scope: 'all-time',
  },
  'hero-median': {
    what: 'Your middle score: half your rounds were higher, half lower.',
    computed: [
      'Line up all your scores from lowest to highest and take the one in the middle (the average of the middle two when there is an even number).',
      'The round-type filter applies.',
    ],
    scope: 'all-time',
  },
  'hero-best': {
    what: 'Your highest single-round score out of 50, for the round types picked in the filter.',
    computed: [
      'The top score across every round you have shot. The round-type filter applies.',
      'The date it was first reached is in Personal bests.',
    ],
    scope: 'all-time',
    terms: ['round-types'],
  },
  'win-rounds': {
    what: 'How many rounds you shot inside the time window, for the round types picked in the filter.',
    computed: [
      'Every round on a Sunday between the window’s first and last date, including second rounds on the same day.',
    ],
    scope: 'windowed',
    terms: ['round-types', 'time-window'],
  },
  'win-average': {
    what: 'Your typical score out of 50 inside the time window.',
    read: [
      'Compare it with your lifetime average below to see whether you are running hot or cold.',
    ],
    computed: [
      'The scores of your rounds in the window added up, divided by how many rounds that is.',
      'The round-type filter applies.',
    ],
    scope: 'windowed',
    terms: ['time-window'],
  },
  'win-best': {
    what: 'Your highest single-round score inside the time window.',
    computed: ['The top score among your rounds in the window. The round-type filter applies.'],
    scope: 'windowed',
    terms: ['time-window'],
  },
  odometer: {
    what: 'Lifetime totals for everything you have ever shot. The round-type filter does not change these.',
    read: [
      'Hit rate is the share of targets you broke.',
      'Streaks count Sundays in a row you showed up.',
    ],
    computed: [
      'Clays thrown = rounds × 50. Clays broken = all your scores added up. Hit rate = broken ÷ thrown.',
      'Streaks count only Sundays with complete results; other Sundays neither add to nor break one. The current streak counts back from the latest (0 if you missed it).',
      'Favorite month = the month (any year) you have shot most often; ties go to the earlier month.',
    ],
    scope: 'all-time',
    terms: ['clays-thrown', 'streak'],
  },
  'floor-ceiling': {
    what: 'The low and high end of your normal recent scoring: a bad-but-normal day and a good-but-normal day.',
    read: [
      '“34.0 / 46.0” means that of your last 20 rounds, about 2 were 34 or lower and about 2 were 46 or higher.',
      'A wide gap means streaky; a narrow gap means steady.',
    ],
    computed: [
      'Line up your last 20 rounds (fewer if you have not shot 20) from lowest to highest. Low end = the score a tenth of the way up; high end = nine-tenths of the way up. Landing between two scores gives decimals like 36.4.',
      'Every round counts. Needs at least 8 rounds. The round-type filter does not apply.',
    ],
    terms: ['streak'],
  },
  'bad-day': {
    what: 'How often you shoot a round well below what we expected of you that day.',
    read: [
      '10% means about 1 round in 10 is a clunker.',
      'Lower is better. Compare with your own past; nobody is at 0%.',
    ],
    computed: [
      'Expected score = your rating going into the day, moved up or down by how everyone else did that day (a tough day lowers it).',
      'A bad round is 6 or more targets under expected. Rate = bad rounds ÷ all your rounds on Sundays with complete results, over your whole career.',
      'The round-type filter does not apply.',
    ],
    scope: 'all-time',
  },
  form: {
    what: 'Whether you have been beating or missing your expected score lately.',
    read: [
      '“Hot (+3.4)” means over your last 5 rounds you averaged 3.4 targets above expected. Cold is the same below. Anything between is Steady.',
      'A dash means you do not have 5 counted rounds yet.',
    ],
    computed: [
      'For each round: your score minus your expected score (see Bad-day rate). Form = the average of that over your last 5 rounds on Sundays with complete results. A second round the same day counts as a round.',
      'Hot is +3 or more; Cold is −3 or less. The round-type filter does not apply.',
    ],
  },
  wins: {
    what: 'How many Sundays you finished first, and how many in the top three.',
    read: ['“3 / 9” means 3 wins and 9 top-three finishes (the 3 wins are part of the 9).'],
    computed: [
      'Each Sunday only your best round counts, ranked against everyone else’s best round. A win is 1st; a podium is 1st to 3rd. Ties share the place.',
      'Every Sunday counts, including small turnouts and Sundays with incomplete results.',
      'The round-type filter does not apply.',
    ],
    scope: 'all-time',
  },
  'field-beaten': {
    what: 'On a typical Sunday, the share of the other shooters you beat.',
    read: [
      '50% is the middle of the pack. 80% means you usually beat about 4 in 5. 100% means you won every time.',
    ],
    computed: [
      'Each Sunday with complete results: your best round against everyone else’s best round. That day’s number = shooters you beat ÷ other shooters there, with a tie counting as half. Beat 6 of 9 and tied 1: (6 + 0.5) ÷ 9 = 72%. Alone that day counts as 100%.',
      'Then those daily numbers are averaged. The round-type filter does not apply.',
    ],
    scope: 'all-time',
  },
  peak: {
    what: 'The highest your rating has ever been, and when.',
    read: [
      'Rating is our estimate of your skill in targets out of 50 on a typical Sunday (see the Rating chart).',
      'A current rating well below the peak means you are off your best.',
    ],
    computed: [
      'The highest point on your Rating line; if tied, the earliest date.',
      'Every point counts, including your first few Sundays when the estimate is still rough. The round-type filter does not apply.',
    ],
    scope: 'all-time',
  },
  rust: {
    what: 'Whether you shoot worse than usual on your first Sunday back after a break.',
    read: [
      '“−2.1 after 3+ weeks off (4 rounds; club −1.0)” means coming back you shoot about 2 targets worse than your usual, over 4 rounds. The club loses about 1.',
      'Positive means you come back sharp. One or two rounds is mostly luck, so a number needs at least 3 rounds.',
    ],
    computed: [
      'A break is 28 or more days between two Sundays you shot (3 Sundays skipped).',
      'Rust = your average (score minus expected score) on your first Sunday back, minus the same on all your other rounds. Only Sundays with complete results count.',
      'Club = the same over everyone’s rounds together. The round-type filter does not apply.',
    ],
    scope: 'all-time',
  },
  milestone: {
    what: 'Your next Sunday-count milestone (10, 25, 50, 100, 150, 200 or 250) and roughly when you will reach it.',
    read: [
      '“50 Sundays — 6 to go, projected Mar 8, 2027” means you have shot 44 different Sundays, and at your recent pace you will hit 50 around that date.',
    ],
    computed: [
      'Count = different days you have shot, any round type, complete results or not.',
      'Pace = Sundays you shot in the last 26 weeks ÷ 26. Projected date = today + (Sundays to go ÷ pace) weeks, rounded up to a whole week. No date if you have not shot in 26 weeks.',
    ],
    scope: 'all-time',
    terms: ['round-types'],
  },
  pbs: {
    what: 'Your highest round ever, and your highest in each calendar year, with the date.',
    read: [
      'Years are listed newest first. Tap a date to open that Sunday.',
      '“early” marks a best from your first 5 rounds. It stays in the table but is not a new personal best on the chart or in trophies.',
    ],
    computed: [
      'The highest score among all your rounds (or that year’s rounds). If you shot it more than once, the earliest date is shown.',
      'A best is early when you had fewer than 5 rounds on earlier days. The round-type filter applies.',
    ],
    scope: 'all-time',
    terms: ['personal-best'],
  },
} satisfies Record<string, Explainer>;
