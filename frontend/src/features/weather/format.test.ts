import { describe, expect, it } from 'vitest';
import { DIMENSION_LABELS, bandLabel, formatEffect, formatSigned } from './format';

describe('weather formatting', () => {
  it('labels bands with their units', () => {
    expect(bandLabel('temp_band', '55-70')).toBe('55-70 °F');
    expect(bandLabel('wind_band', '20+')).toBe('20+ mph');
    expect(bandLabel('precip_band', 'wet')).toBe('Wet');
    expect(bandLabel('precip_band', 'dry')).toBe('Dry');
    expect(bandLabel('precip_band', 'hail')).toBe('hail');
    expect(bandLabel('condition', 'partly_cloudy')).toBe('Partly cloudy');
    expect(bandLabel('condition', 'fog')).toBe('fog');
    expect(bandLabel('time_of_year', 'winter')).toBe('Winter');
    expect(bandLabel('time_of_year', 'spring')).toBe('Spring');
    expect(bandLabel('time_of_year', 'summer')).toBe('Summer');
    expect(bandLabel('time_of_year', 'fall')).toBe('Fall');
    expect(bandLabel('time_of_year', 'monsoon')).toBe('monsoon');
    expect(DIMENSION_LABELS.time_of_year).toBe('Time of year');
  });

  it('signs numbers with a real minus and never shows -0.0', () => {
    expect(formatSigned(0.44)).toBe('+0.4');
    expect(formatSigned(-1.25)).toBe('−1.2');
    expect(formatSigned(-0.04)).toBe('0.0');
  });

  it('describes a per-unit effect', () => {
    expect(formatEffect(-0.62, 'gust_mph')).toBe('−0.6 targets per 10 mph more gust');
    expect(formatEffect(0.281, 'temp_f')).toBe('+0.3 targets per 10 °F warmer');
    expect(formatEffect(0, 'precip_in')).toBe('0.0 targets per 0.1 in more rain');
  });
});
