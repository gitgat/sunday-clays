import type { Explainer } from '../../components/charts/types';

/**
 * Plain-language explainer copy for the weather feature (see .superpowers/sdd/explainers/STYLE.md).
 * Keys are the page's ChartFrame `urlKey`s plus stat ids for the two non-chart stat blocks. Every number
 * below is what backend/src/sunday_clays/analytics/weather_effects.py computes.
 */

export const explainers: Record<string, Explainer> = {
  wf: {
    what: 'How hard each Sunday was, plotted against the weather that morning. Dots are Sundays; the line is what the club-wide weather model expects.',
    read: [
      'A line that slopes up means Sundays with more of that weather were harder (scores came out lower).',
      'A flat line means that weather made little difference on its own.',
      'Dots far from the line were harder or easier than the weather alone explains.',
    ],
    computed: [
      'Difficulty is in targets: how many fewer targets than a typical day the field broke, once each shooter’s own skill is allowed for. Positive means harder.',
      'Dots are the Sundays in the chosen time window; fullscreen and the CSV download show every Sunday with weather.',
      'The line is fitted on every Sunday with full results and weather, all the way back, not just the window. It uses temperature, gusts, rain and cloud together, and Sundays with more rounds count for more. It shows the chosen measure with the other three held at their averages.',
      'Weather is the 10:00 to 12:00 window.',
      'The round-type filter applies.',
    ],
    scope: 'windowed',
  },
  wr: {
    what: 'The typical score on Sundays, grouped by the direction the wind blew from.',
    read: [
      'A longer bar means the middle score was higher when the wind came from that direction.',
      'A direction with no bar has no Sundays.',
    ],
    computed: [
      'For each Sunday in the chosen time window with full results: the median score (the middle score of everyone who shot). Fullscreen and the CSV download use every Sunday with weather on record.',
      'Each Sunday goes into one of 8 compass points by where the wind came from, and the bars are the average of those medians. Every direction is on a 0 to 50 scale.',
      'The round-type filter applies.',
    ],
    scope: 'windowed',
  },
  wb: {
    what: 'The average score in each kind of weather or time of year.',
    read: [
      'Taller bars mean higher scores in that weather.',
      'Check the number of Sundays behind a bar in the table: a bar built from one or two Sundays says little.',
    ],
    computed: [
      'Sundays in the chosen time window with full results and weather are put into bands (for example 55-70 °F or 10-20 mph gusts). Fullscreen and the CSV download use every Sunday with weather on record.',
      'Time of year groups Sundays by month: winter is December to February, spring March to May, summer June to August and fall September to November. A time of year with no Sundays in the window has no bar, so a short window shows only some of them.',
      'Each bar is the average of every round shot on those Sundays. All rounds count, including second rounds.',
      'The round-type filter applies.',
    ],
    scope: 'windowed',
  },
  wt: {
    what: 'How many people came out in each kind of weather or time of year.',
    read: [
      'Taller bars mean bigger turnouts in that weather.',
      'A band with few Sundays can be a fluke, so use the table to see how many.',
    ],
    computed: [
      'Every Sunday in the chosen time window with weather and a recorded head count, including days with attendance only and no scores. Fullscreen and the CSV download use every Sunday with weather on record.',
      'Time of year groups Sundays by month: winter is December to February, spring March to May, summer June to August and fall September to November. A time of year with no Sundays in the window has no bar.',
      'Each bar is the average head count of the Sundays in that band.',
      'The round-type filter does not apply.',
    ],
    scope: 'windowed',
  },
  ws: {
    what: 'How much each shooter’s scores have tended to move in warmer, windier or wetter weather, beyond how hard the day was.',
    read: [
      'Bars to the right mean scores rose with more of that weather; bars to the left mean they fell. It describes a pattern, not a ranking.',
      'Bars close to zero mean weather made little difference.',
      'Only the 12 biggest effects are drawn here; fullscreen draws everyone, and the table and CSV list everyone.',
    ],
    computed: [
      'For each shooter with at least 10 rounds with weather: compare their score with what we expected for them that day, against the weather that day. That gives targets gained or lost per 10 °F, 10 mph of gust or 0.1 in of rain.',
      'Each estimate is then pulled toward zero, more so when the shooter has few rounds, so a few odd days do not swing it.',
      'When the rounds cannot tell shooters apart on a measure, every estimate becomes zero, so no one shows a weather effect at all. Then you get a short note instead of bars.',
      'Every round counts and the round-type filter does not apply.',
      'It looks at all history, whatever time window is chosen.',
    ],
    scope: 'all-time',
  },
  conditions: {
    what: 'Pick a range of weather and see how the Sundays that fit it compare with every Sunday in the same time window.',
    computed: [
      'Only Sundays in the chosen time window with full results and weather are counted. The temperature range, gust limit and rain choice all have to match.',
      'The Matching column is the Sundays that fit your choices. The All column is every Sunday in the time window, so it is named after that period (for example “All, last 12 months”).',
      'Mean field median: the average of each Sunday’s middle score.',
      'Mean difficulty: the average difficulty in targets; positive means harder than a typical day.',
      'The ends of each slider are open: 20 °F or colder, 100 °F or warmer and 40+ mph gusts include everything beyond them.',
      'The round-type filter applies.',
    ],
    scope: 'windowed',
  },
  'profile-sensitivity': {
    what: 'How your scores have moved with weather, beyond how hard each day was.',
    read: [
      'Plus means you have tended to score higher in more of that weather; minus means lower.',
      'Numbers close to zero mean weather has made little difference to you.',
    ],
    computed: [
      'Needs at least 10 of your rounds with a weather record.',
      'We compare your score with what we expected for you that day, against the temperature, gusts and rain. The result is targets per 10 °F, 10 mph of gust or 0.1 in of rain.',
      'Estimates are pulled toward zero when you have few rounds. Every round counts, all history is used and the round-type filter does not apply.',
    ],
    scope: 'all-time',
  },
};
