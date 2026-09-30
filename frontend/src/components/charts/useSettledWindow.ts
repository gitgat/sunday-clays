import { skipToken, useQuery } from '@tanstack/react-query';
import { useTimeWindow, type WindowRange } from '../../lib/timeWindow';

/**
 * The active time window's date range, and whether it is known yet. `settled` turns true once
 * GET /api/meta (which useTimeWindow fetches) has answered or failed, so a query that follows the
 * window can wait for it instead of running twice, while a fresh install with nothing scored
 * (`range` null) still loads.
 */
export function useSettledWindow(): {
  settled: boolean;
  range: WindowRange | null;
  label: string;
} {
  const { range, label } = useTimeWindow();
  // Same key as useTimeWindow's query, so this only watches its state: skipToken never fetches.
  const meta = useQuery({ queryKey: ['/api/meta'], queryFn: skipToken });
  return { settled: !meta.isPending, range, label };
}
