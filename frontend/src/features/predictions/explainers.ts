import type { Explainer } from '../../components/charts/types';

/**
 * Plain-language copy for the Next Sunday card and profile outlook. Every statement matches
 * backend/src/sunday_clays/analytics/predictions.py (skill.predict, weather_effects.club_regression).
 */
export const explainers = {
  'next-sunday': {
    what: 'A best guess at how the field will shoot next Sunday, from the weather forecast and how everyone has been shooting lately.',
    read: [
      'The predicted field median is the middle score expected from the people likely to come.',
      'A shooter’s expected score is the single most likely result for that shooter. The likely range is where about two out of three of their scores land, so a result outside it is normal too.',
      'Nothing here ranks anyone. It is a guess, not a promise.',
    ],
    computed: [
      'Expected score = the shooter’s current skill rating + the club level − how hard the day looks. The skill rating moves a little after every round they shoot.',
      'How hard the day looks comes from the club weather model: past Sundays’ difficulty against temperature, wind gusts, rain and cloud, applied to the 10:00 to 12:00 forecast. Without a forecast it assumes a typical Sunday. Positive means harder, so scores come out lower.',
      'Likely range = expected score plus or minus one typical spread, clipped to 0 to 50. The spread adds up how unsure the rating is, how much a single round bounces around, and how unsure the day’s difficulty is.',
      'Who is likely to come: the shooters who came to at least one of the last 13 Sundays with scores. Their chance of coming is the number of those Sundays they shot, out of 13.',
      'Predicted field median = the middle expected score among those shooters, counting each in proportion to their chance of coming. Expected turnout = the chances of coming, added up.',
      'Recomputed after every analytics run, and the forecast refreshes twice a day.',
    ],
  },
} as const satisfies Record<string, Explainer>;
