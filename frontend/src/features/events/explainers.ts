import type { Explainer } from '../../components/charts/types';

/**
 * Plain-language copy for the Sunday pages, keyed by chart urlKey or stat id. Written against
 * analytics/metrics.py, analytics/skill.py, domain/rebuild.py, weather/aggregate.py and
 * api/routes/events.py (STYLE.md: no jargon, neutral pronouns, "Sunday" not "event").
 */
const explainers = {
  calendar: {
    what: 'Every Sunday of the year as a square. Tap one the club shot to open its results.',
    read: [
      'Solid means scores were entered. Outlined means the club met but no scores were entered.',
      'Dashed means that Sunday was a different round type from your filter. Faded means nothing is on file.',
    ],
    computed: [
      'One square per Sunday, plus any shoot on another day.',
      'Solid = at least one round was entered.',
      'The year is set with the arrows at the top. A custom time window opens on the year it ends in.',
    ],
    scope: 'year',
    terms: ['round-types', 'time-window'],
  },
  stn: {
    what: 'The targets each shooter broke at each station on this Sunday. Only Sundays with a station sheet show it.',
    read: [
      'Rows are shooters, columns are stations. The colour bar shows which shade means more hits.',
      'A column that is low for everyone was a tough station.',
    ],
    computed: [
      'Each cell is the targets broken at that station, straight from the station sheet.',
      'It is a count, not a share: 4 of 5 and 4 of 10 look the same.',
      'Colours run from the lowest to the highest cell that day.',
    ],
  },
  results: {
    what: 'Every round shot this Sunday, best score first.',
    read: [
      '"T3" is a tie for third; "R2" is a second round.',
      '"Vs middle score" of +5.0 means 5 targets above the middle score that day.',
    ],
    computed: [
      'Ties share the higher place: two 47s are both T1, the next is 3rd.',
      'Vs middle score = the round\'s score minus the middle score (median) of every round that day. "—" on partial-results Sundays.',
      'Rating change = how far this Sunday moved the rating (skill estimate out of 50); "—" if ratings did not move.',
    ],
  },
  shooters: {
    what: 'How many people have at least one recorded score this Sunday.',
    computed: [
      'Counts shooters with a recorded round, not everyone who came.',
      'Compare with Head count: a lower number means some scores are missing.',
    ],
  },
  headCount: {
    what: 'How many people the attendance sheet says came this Sunday.',
    computed: [
      'The number from the attendance sheet; "—" when there is no attendance sheet for this day.',
      'When under half of the head count has scores, the Sunday is marked as partial results.',
    ],
  },
  median: {
    what: 'The middle score of the day: half the rounds were this or better, half this or worse.',
    read: ['A .5 means the two middle rounds were one target apart.'],
    computed: [
      'Every round shot that day counts, second rounds included.',
      'Rounds are sorted by score and the middle one is taken.',
    ],
  },
  topScore: {
    what: 'The best single round shot this Sunday, out of 50.',
    computed: ['The highest score among all rounds that day, second rounds included.'],
  },
  difficulty: {
    what: 'How much harder or easier the course played than a typical Sunday of the past year, allowing for who showed up.',
    read: [
      '+2.0 (harder) means shooters broke about 2 fewer targets than usual for them.',
      'Negative is easier. 0.0 is typical. A low median with new shooters does not make a hard day.',
    ],
    computed: [
      'Each shooter: average score that day minus rating going in. Gaps are averaged; settled shooters count more.',
      "Difficulty = the typical gap over the last 52 weeks of full-results Sundays, minus this Sunday's.",
      'Small fields are pulled toward 0.0. "—" for partial results.',
    ],
    terms: ['difficulty'],
  },
  weather: {
    what: "Weather from 10:00 to 12:00, from a weather service's hourly records (not a gauge at the range).",
    read: [
      '"Feels" allows for wind and humidity. Wind shows average speed, direction it blew from, then the strongest gust.',
    ],
    computed: [
      'Temperature, wind, cloud, humidity and pressure average the 10:00, 11:00 and 12:00 readings.',
      'Rain is the total; the gust is the strongest.',
      'Conditions, first match wins: Rain (0.02 in or more), Windy (gusts 20 mph or more), Overcast (cloud 75%+), Partly cloudy (30%+), else Clear.',
    ],
  },
  vsPrev: {
    what: 'This Sunday against the previous Sunday with full results: head count, median, top score and difficulty.',
    read: [
      '+6 head count means six more people came. −2.0 median means the middle score was two targets lower.',
      'A positive difficulty means this Sunday played harder.',
    ],
    computed: [
      "Each figure is this Sunday's number minus the earlier Sunday's.",
      'The earlier Sunday is the latest one with full results, of any round type, however many weeks back.',
      '"—" when either Sunday lacks the number.',
    ],
    terms: ['difficulty', 'held-sunday', 'round-types'],
  },
  notables: {
    what: 'Other highlights from this Sunday. Personal bests and first-timers are in the insights at the top of the page.',
    read: ['Each line names the shooter and what happened.'],
    computed: ['All round types count together.'],
    terms: ['first-timer', 'round-types'],
  },
  stations: {
    what: 'How many stations were shot on this Sunday.',
    computed: ['Counted from the station sheet; "—" when there is none.'],
  },
  special: {
    what: 'A special shoot is a Sunday with its own format and number of targets, such as a 60-target 3-bird shoot.',
    read: [
      "Scores are targets broken out of that shoot's own total, best first. Nobody is ranked or rated.",
    ],
    computed: [
      'It counts as a Sunday shot for everyone who came: Sundays shot, streaks and attendance trophies include it.',
      'Its scores stay out of averages, best scores, records, ratings and leaderboards, which are all out of 50.',
    ],
    terms: ['special-shoot', 'streak'],
  },
} satisfies Record<string, Explainer>;

/** Typed by key, so a wired-in lookup is never undefined. */
export const eventExplainers: Record<keyof typeof explainers, Explainer> = explainers;
