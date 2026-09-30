import { useRoundTypes } from '../../../lib/roundTypes';

/**
 * Appended to the subtitle of a club chart whose endpoint takes no `round_type` (C8): with the
 * global round-type filter on, it says the chart still counts every round type, so its numbers
 * do not seem to contradict the filtered stats beside it.
 */
export function useUnfilteredNote(): string {
  const [roundTypes] = useRoundTypes();
  return roundTypes.length > 0 ? ' · all round types' : '';
}
