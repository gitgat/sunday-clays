import { http, HttpResponse } from 'msw';
import type { components } from '../../api/schema';

type Schemas = components['schemas'];

const four: Schemas['StationStatOut'] = {
  label: '4',
  station_no: 4,
  era: 0,
  era_start: null,
  hits: 184,
  n_targets: 259,
  n_rounds: 37,
  n_events: 2,
  hit_pct: 0.710425,
  ci_low: 0.644151,
  ci_high: 0.768786,
  deff: 1.291872,
  clean_rate: 0.135135,
  separator: 0.32,
  leaders: [
    {
      shooter_id: 7,
      display_name: 'McGinnis, Alvin',
      hits: 20,
      n_targets: 21,
      n_rounds: 3,
      hit_pct: 0.952381,
    },
  ],
};

const nine: Schemas['StationStatOut'] = {
  label: '9',
  station_no: 9,
  era: 0,
  era_start: null,
  hits: 130,
  n_targets: 259,
  n_rounds: 37,
  n_events: 2,
  hit_pct: 0.501931,
  ci_low: 0.432572,
  ci_high: 0.571215,
  deff: 1.321341,
  clean_rate: 0,
  separator: 0.615142,
  leaders: [],
};

export const stationsFixture: Schemas['StationsOut'] = {
  era: 'current',
  n_events: 2,
  last_reset_date: null,
  coverage: {
    n_station_sundays: 2,
    first_date: '2026-09-06',
    last_date: '2026-09-13',
    n_scored_sundays: 311,
    latest_date: '2026-09-13',
  },
  stations: [four, nine],
  by_event: [
    {
      event_date: '2026-09-06',
      label: '4',
      station_no: 4,
      hits: 120,
      n_targets: 168,
      hit_pct: 0.714286,
    },
    {
      event_date: '2026-09-06',
      label: '9',
      station_no: 9,
      hits: 86,
      n_targets: 168,
      hit_pct: 0.511905,
    },
    {
      event_date: '2026-09-13',
      label: '4',
      station_no: 4,
      hits: 64,
      n_targets: 91,
      hit_pct: 0.703297,
    },
    {
      event_date: '2026-09-13',
      label: '9',
      station_no: 9,
      hits: 44,
      n_targets: 91,
      hit_pct: 0.483516,
    },
  ],
  matrix: [
    {
      shooter_id: 12,
      display_name: 'Hadley, Ike',
      label: '4',
      station_no: 4,
      hits: 12,
      n_targets: 14,
      n_rounds: 3,
      hit_pct: 0.857143,
    },
    {
      shooter_id: 12,
      display_name: 'Hadley, Ike',
      label: '9',
      station_no: 9,
      hits: 7,
      n_targets: 14,
      n_rounds: 2,
      hit_pct: 0.5,
    },
  ],
  resets: [],
};

export const stationDetailFixture: Schemas['StationDetailOut'] = {
  label: '4',
  station_no: 4,
  eras: [
    {
      ...four,
      era: 0,
      era_start: null,
      hits: 120,
      n_targets: 168,
      n_rounds: 24,
      n_events: 1,
      hit_pct: 0.714286,
      leaders: [],
    },
    {
      ...four,
      era: 1,
      era_start: '2026-09-10',
      hits: 64,
      n_targets: 91,
      n_rounds: 13,
      n_events: 1,
      hit_pct: 0.703297,
      leaders: [],
    },
  ],
  by_event: [
    {
      event_date: '2026-09-06',
      label: '4',
      station_no: 4,
      hits: 120,
      n_targets: 168,
      hit_pct: 0.714286,
    },
    {
      event_date: '2026-09-13',
      label: '4',
      station_no: 4,
      hits: 64,
      n_targets: 91,
      hit_pct: 0.703297,
    },
  ],
  leaders: four.leaders,
  wind: [
    {
      band: '<10',
      band_order: 4.2,
      hit_pct: 0.72,
      ci_low: 0.65,
      ci_high: 0.78,
      n_targets: 280,
      n_events: 6,
      sufficient: true,
    },
    {
      band: '20+',
      band_order: 22.5,
      hit_pct: 0.61,
      ci_low: 0.48,
      ci_high: 0.72,
      n_targets: 70,
      n_events: 2,
      sufficient: false,
    },
  ],
  resets: [{ label: '4', station_no: 4, effective_date: '2026-09-10', note: 'New trap angle' }],
};

export const shooterStationsFixture: Schemas['ShooterStationsOut'] = {
  shooter_id: 12,
  last_reset_date: null,
  coverage: {
    n_rounds: 3,
    n_sundays: 2,
    first_date: '2026-09-06',
    last_date: '2026-09-13',
    latest_date: '2026-09-13',
  },
  stations: [
    {
      label: '4',
      station_no: 4,
      hits: 12,
      n: 14,
      n_rounds: 2,
      hit_pct: 0.857143,
      field_pct: 0.710425,
      delta: 0.048,
    },
    {
      label: '9',
      station_no: 9,
      hits: 3,
      n: 7,
      n_rounds: 1,
      hit_pct: 0.428571,
      field_pct: 0.501931,
      delta: -0.025,
    },
  ],
};

export const handlers = [
  http.get('*/api/stations', () => HttpResponse.json(stationsFixture)),
  http.get('*/api/stations/:label', ({ params }) => {
    const label = String(params.label).toUpperCase();
    return HttpResponse.json({ ...stationDetailFixture, label, station_no: parseInt(label, 10) });
  }),
  http.get('*/api/shooters/:id/stations', () => HttpResponse.json(shooterStationsFixture)),
];
