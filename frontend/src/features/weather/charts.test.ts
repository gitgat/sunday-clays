import { describe, expect, it } from 'vitest';
import type { WeatherShooter } from './api';
import {
  SENSITIVITY_CHART_ROWS,
  bandScoreChart,
  difficultyFitChart,
  sensitivityChart,
  turnoutChart,
  windRoseChart,
} from './charts';
import { WEATHER_EFFECTS, WEATHER_EVENTS, WEATHER_SENSITIVITY, WEATHER_TURNOUT } from './mocks';

describe('difficultyFitChart', () => {
  it('plots scored events and the partial-effect line of the club model', () => {
    const { data, option } = difficultyFitChart(WEATHER_EVENTS, WEATHER_EFFECTS.model, 'gust_mph');
    expect(data.rows).toEqual([
      { event_date: '2026-08-16', x: 12, difficulty: -1.5 },
      { event_date: '2026-09-13', x: 25, difficulty: 1.2 },
      { event_date: '2026-09-27', x: 6, difficulty: -0.5 },
    ]);
    // others at their means: 1 - 0.02*60 + 2*0.05 + 0.01*50 = 0.4; line = 0.4 + 0.1 * gust
    expect(option.series).toEqual([
      expect.objectContaining({
        type: 'scatter',
        data: [
          [12, -1.5],
          [25, 1.2],
          [6, -0.5],
        ],
      }),
      expect.objectContaining({
        type: 'line',
        data: [
          [6, 1],
          [25, 2.9],
        ],
      }),
    ]);
  });

  it('draws no line without a model or without points', () => {
    expect(difficultyFitChart(WEATHER_EVENTS, null, 'temp_f').option.series).toHaveLength(1);
    const unscored = WEATHER_EVENTS.map((e) => ({ ...e, difficulty: null }));
    const { data, option } = difficultyFitChart(unscored, WEATHER_EFFECTS.model, 'temp_f');
    expect(data.rows).toEqual([]);
    expect(option.series).toHaveLength(1);
  });
});

describe('windRoseChart', () => {
  it('averages field medians per compass sector and skips missing directions', () => {
    const { data, option } = windRoseChart(WEATHER_EVENTS);
    expect(data.rows.filter((r) => r['events'] !== 0)).toEqual([
      { sector: 'S', events: 1, median: 34 },
      { sector: 'W', events: 1, median: 39 },
    ]);
    expect(data.rows).toHaveLength(8);
    expect(option.series).toEqual([
      expect.objectContaining({
        coordinateSystem: 'polar',
        data: [null, null, null, null, 34, null, 39, null],
      }),
    ]);
  });
});

describe('band charts', () => {
  it('shows mean scores per band of the chosen dimension', () => {
    const { data, option } = bandScoreChart(WEATHER_EFFECTS.bands, 'temp_band');
    expect(data.rows).toEqual([
      { band: '55-70 °F', events: 2, rounds: 36, mean_score: 36.5, mean_difficulty: 0.35 },
      { band: '70-85 °F', events: 1, rounds: 48, mean_score: 37.35, mean_difficulty: -1.5 },
    ]);
    expect(option.xAxis).toMatchObject({ data: ['55-70 °F', '70-85 °F'] });
    expect(bandScoreChart(WEATHER_EFFECTS.bands, 'condition').data.rows).toEqual([
      { band: 'Rain', events: 1, rounds: 13, mean_score: 34.46, mean_difficulty: null },
    ]);
    const blank = [
      {
        dimension: 'temp_band',
        band: '55-70',
        n_events: 1,
        n_rounds: 0,
        mean_score: null,
        mean_difficulty: null,
      },
    ];
    expect(bandScoreChart(blank, 'temp_band').option.series).toEqual([
      expect.objectContaining({ data: [null] }),
    ]);
  });

  it('groups scores and turnout by time of year in server order', () => {
    expect(bandScoreChart(WEATHER_EFFECTS.bands, 'time_of_year').data.rows).toEqual([
      { band: 'Summer', events: 1, rounds: 48, mean_score: 37.35, mean_difficulty: -1.5 },
      { band: 'Fall', events: 2, rounds: 36, mean_score: 36.5, mean_difficulty: 0.35 },
    ]);
    expect(turnoutChart(WEATHER_TURNOUT, 'time_of_year').data.rows).toEqual([
      { band: 'Winter', events: 1, mean: 7, median: 7 },
      { band: 'Fall', events: 2, mean: 18, median: 18 },
    ]);
  });

  it('shows mean head counts per band', () => {
    const { data } = turnoutChart(WEATHER_TURNOUT, 'temp_band');
    expect(data.rows).toEqual([
      { band: '<40 °F', events: 1, mean: 7, median: 7 },
      { band: '55-70 °F', events: 2, mean: 18, median: 18 },
    ]);
  });
});

describe('sensitivityChart', () => {
  it('lists every estimated shooter, most negative first, ties by name', () => {
    const twin: WeatherShooter = {
      shooter_id: 3,
      display_name: 'Marsden, Wylie',
      n_rounds: 12,
      terms: [{ covariate: 'gust_mph', beta: -0.5, se: 0.3, shrunk: -0.4, per_unit: -0.62 }],
    };
    const { data, option } = sensitivityChart([...WEATHER_SENSITIVITY.shooters, twin], 'gust_mph');
    expect(data.rows).toEqual([
      { shooter: 'Hadley, Ike', rounds: 78, effect: -0.62 },
      { shooter: 'Marsden, Wylie', rounds: 12, effect: -0.62 },
      { shooter: 'Abernathy, Preston', rounds: 80, effect: 0.15 },
    ]);
    expect(option.yAxis).toMatchObject({
      data: ['Hadley, Ike', 'Marsden, Wylie', 'Abernathy, Preston'],
    });
    expect(sensitivityChart(WEATHER_SENSITIVITY.shooters, 'precip_in').data.rows).toEqual([
      { shooter: 'Abernathy, Preston', rounds: 80, effect: 0 },
    ]);
  });

  it('draws only the largest effects', () => {
    const many: WeatherShooter[] = Array.from({ length: 14 }, (_, i) => ({
      shooter_id: i + 1,
      display_name: `Shooter ${String(i + 1).padStart(2, '0')}`,
      n_rounds: 20,
      terms: [{ covariate: 'temp_f', beta: 1, se: 1, shrunk: 1, per_unit: i - 6 }],
    }));
    const { data, option } = sensitivityChart(many, 'temp_f');
    expect(data.rows).toHaveLength(14);
    const axis = option.yAxis as { data: string[] };
    expect(axis.data).toHaveLength(SENSITIVITY_CHART_ROWS);
    // |effect| ranks: 7 (Shooter 14), 6 (01, 13), 5 (02, 12), ... 1 (06, 08): 08 is cut
    expect(axis.data).not.toContain('Shooter 07');
    expect(axis.data).not.toContain('Shooter 08');
    expect(axis.data[0]).toBe('Shooter 01');
  });

  it('uses ECharts 6 label containment and zero-based bars', () => {
    const grids = [
      difficultyFitChart(WEATHER_EVENTS, null, 'gust_mph').option.grid,
      bandScoreChart(WEATHER_EFFECTS.bands, 'temp_band').option.grid,
      turnoutChart(WEATHER_TURNOUT, 'temp_band').option.grid,
    ];
    for (const grid of grids) {
      expect(grid).not.toHaveProperty('containLabel');
      expect(grid).toMatchObject({ outerBoundsMode: 'same', outerBoundsContain: 'axisLabel' });
    }
    expect(bandScoreChart(WEATHER_EFFECTS.bands, 'temp_band').option.yAxis).not.toHaveProperty(
      'scale',
    );
  });

  it('keeps the sensitivity axis name inside the chart, symmetric about zero, with no zoom slider', () => {
    const { option, flat } = sensitivityChart(
      WEATHER_SENSITIVITY.shooters,
      'gust_mph',
      WEATHER_SENSITIVITY.tau2,
    );
    expect(flat).toBe(false);
    expect(option.grid).toMatchObject({ outerBoundsMode: 'same', outerBoundsContain: 'all' });
    expect(option.xAxis).toMatchObject({
      name: 'Targets gained or lost',
      nameLocation: 'middle',
      min: -0.7,
      max: 0.7,
    });
    expect(option).not.toHaveProperty('dataZoom');
  });

  it('is flat when the between-shooter spread is zero or every effect is zero', () => {
    expect(
      sensitivityChart(WEATHER_SENSITIVITY.shooters, 'temp_f', [{ covariate: 'temp_f', tau2: 0 }])
        .flat,
    ).toBe(true);
    expect(
      sensitivityChart(WEATHER_SENSITIVITY.shooters, 'precip_in', WEATHER_SENSITIVITY.tau2).flat,
    ).toBe(true);
    expect(sensitivityChart(WEATHER_SENSITIVITY.shooters, 'temp_f').flat).toBe(false);
    expect(sensitivityChart([], 'temp_f', WEATHER_SENSITIVITY.tau2).flat).toBe(false);
  });

  it('truncates long shooter names on the sensitivity axis', () => {
    const { option } = sensitivityChart(WEATHER_SENSITIVITY.shooters, 'gust_mph');
    expect(option.yAxis).toMatchObject({ axisLabel: { width: 96, overflow: 'truncate' } });
  });

  it('draws every shooter when the limit is lifted', () => {
    const shooters = Array.from({ length: 15 }, (_, i) => ({
      shooter_id: i,
      display_name: `S${String(i).padStart(2, '0')}`,
      n_rounds: 20,
      terms: [{ covariate: 'gust_mph' as const, beta: 1, se: 1, shrunk: 1, per_unit: 1 + i }],
    }));
    const inline = sensitivityChart(shooters, 'gust_mph');
    const all = sensitivityChart(shooters, 'gust_mph', [], Infinity);
    expect((inline.option.yAxis as { data: string[] }).data).toHaveLength(12);
    expect((all.option.yAxis as { data: string[] }).data).toHaveLength(15);
    expect(all.data.rows).toHaveLength(15);
  });
});
