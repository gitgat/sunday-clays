import { useQuery } from '@tanstack/react-query';
import { api, unwrap } from '../../api/client';
import type { components } from '../../api/schema';

export type NextPredictions = components['schemas']['NextPredictionsOut'];
export type PredictedShooter = components['schemas']['PredictionShooterOut'];
export type PredictionForecast = components['schemas']['PredictionForecastOut'];

/** Next Sunday's predictions (C8 `GET /api/predictions/next`); about next Sunday, so never filtered. */
export function useNextPredictions() {
  return useQuery({
    queryKey: ['/api/predictions/next'],
    queryFn: () => unwrap(api.GET('/api/predictions/next')),
  });
}
