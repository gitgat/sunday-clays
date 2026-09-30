import { useQuery } from '@tanstack/react-query';
import { api, unwrap } from '../../api/client';
import type { components } from '../../api/schema';
import { useRoundTypes, type RoundTypeValue } from '../../lib/roundTypes';
import type { WindowRange } from '../../lib/timeWindow';

export type WeatherEvent = components['schemas']['WeatherEventOut'];
export type WeatherEffects = components['schemas']['WeatherEffectsOut'];
export type WeatherModel = components['schemas']['WeatherModelOut'];
export type WeatherBand = components['schemas']['WeatherBandOut'];
export type WeatherSensitivity = components['schemas']['WeatherSensitivityOut'];
export type WeatherShooter = components['schemas']['WeatherShooterOut'];
export type WeatherTurnout = components['schemas']['WeatherTurnoutOut'];

export function useWeatherEvents() {
  return useQuery({
    queryKey: ['/api/weather/events'],
    queryFn: () => unwrap(api.GET('/api/weather/events')),
  });
}

/** `from`/`to` query values for a window; an open start is left out. */
function windowQuery(range: WindowRange): { from?: string; to: string } {
  return range.from === null ? { to: range.to } : { from: range.from, to: range.to };
}

/**
 * Club model + band effects; follows the global round-type filter (C10). The bands cover `range`;
 * the club model is always fitted over all history.
 */
export function useWeatherEffects(range: WindowRange) {
  const [roundTypes] = useRoundTypes();
  return useQuery({
    queryKey: ['/api/weather/effects', roundTypes, range],
    queryFn: () =>
      unwrap(
        api.GET('/api/weather/effects', {
          params: { query: { round_type: roundTypes, ...windowQuery(range) } },
        }),
      ),
  });
}

export function useWeatherSensitivity() {
  return useQuery({
    queryKey: ['/api/weather/sensitivity'],
    queryFn: () => unwrap(api.GET('/api/weather/sensitivity')),
  });
}

/** Head count per band over the Sundays in `range`. */
export function useWeatherTurnout(range: WindowRange) {
  return useQuery({
    queryKey: ['/api/weather/turnout', range],
    queryFn: () =>
      unwrap(api.GET('/api/weather/turnout', { params: { query: windowQuery(range) } })),
  });
}

/** Every Sunday with weather (no window) for the fullscreen and CSV of the band charts. */
export function fetchAllWeatherEffects(roundTypes: RoundTypeValue[]) {
  return unwrap(api.GET('/api/weather/effects', { params: { query: { round_type: roundTypes } } }));
}

export function fetchAllWeatherTurnout() {
  return unwrap(api.GET('/api/weather/turnout', { params: { query: {} } }));
}
