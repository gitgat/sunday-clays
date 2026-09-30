export const MODEL_COVARIATES = ['temp_f', 'gust_mph', 'precip_in', 'cloud_pct'] as const;
export type ModelCovariate = (typeof MODEL_COVARIATES)[number];
export const SENSITIVITY_COVARIATES = ['temp_f', 'gust_mph', 'precip_in'] as const;
export type SensitivityCovariate = (typeof SENSITIVITY_COVARIATES)[number];
export const DIMENSIONS = [
  'temp_band',
  'wind_band',
  'precip_band',
  'condition',
  'time_of_year',
] as const;
export type Dimension = (typeof DIMENSIONS)[number];

export const COVARIATE_LABELS: Record<ModelCovariate, string> = {
  temp_f: 'Temperature (°F)',
  gust_mph: 'Wind gusts (mph)',
  precip_in: 'Rain (in)',
  cloud_pct: 'Cloud cover (%)',
};

export const DIMENSION_LABELS: Record<Dimension, string> = {
  temp_band: 'Temperature',
  wind_band: 'Wind',
  precip_band: 'Rain',
  condition: 'Conditions',
  time_of_year: 'Time of year',
};

const UNIT_PHRASES: Record<SensitivityCovariate, string> = {
  temp_f: 'per 10 °F warmer',
  gust_mph: 'per 10 mph more gust',
  precip_in: 'per 0.1 in more rain',
};

const CONDITION_LABELS: Record<string, string> = {
  rain: 'Rain',
  windy: 'Windy',
  overcast: 'Overcast',
  partly_cloudy: 'Partly cloudy',
  clear: 'Clear',
};

const TIME_OF_YEAR_LABELS: Record<string, string> = {
  winter: 'Winter',
  spring: 'Spring',
  summer: 'Summer',
  fall: 'Fall',
};

/** A band as shown on an axis: temperature and wind bands get their unit; seasons are capitalised. */
export function bandLabel(dimension: Dimension, band: string): string {
  if (dimension === 'temp_band') return `${band} °F`;
  if (dimension === 'wind_band') return `${band} mph`;
  if (dimension === 'condition') return CONDITION_LABELS[band] ?? band;
  if (dimension === 'time_of_year') return TIME_OF_YEAR_LABELS[band] ?? band;
  return band === 'wet' ? 'Wet' : band === 'dry' ? 'Dry' : band;
}

/** Signed with a real minus sign, one decimal: +0.4 / −1.2 / 0.0. */
export function formatSigned(value: number): string {
  const rounded = Math.round(value * 10) / 10;
  if (rounded === 0) return '0.0';
  return rounded > 0 ? `+${rounded.toFixed(1)}` : `−${Math.abs(rounded).toFixed(1)}`;
}

/** "−0.4 targets per 10 mph more gust". */
export function formatEffect(perUnit: number, covariate: SensitivityCovariate): string {
  return `${formatSigned(perUnit)} targets ${UNIT_PHRASES[covariate]}`;
}
