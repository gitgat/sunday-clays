import { describe, expect, it } from 'vitest';
import type { StationMatrix } from './api';
import { stationLongData, stationMatrixModel } from './charts';

// Cells are matched by label, not position: Hadley's first cell list is out of layout order on purpose.
const matrix: StationMatrix = {
  layout: [
    { label: '4', station_no: 4, target_count: 7 },
    { label: '10', station_no: 10, target_count: 8 },
  ],
  entries: [
    {
      entry_row: 10,
      name_key: 'nordquist sherman',
      shooter_id: 12,
      display_name: 'Nordquist, Sherman',
      round_id: 7444,
      hits: [
        { label: '4', station_no: 4, hits: 5 },
        { label: '10', station_no: 10, hits: 7 },
      ],
      total: 12,
    },
    {
      entry_row: 15,
      name_key: 'hadley ike',
      shooter_id: 3,
      display_name: 'Hadley, Ike',
      round_id: 7450,
      hits: [
        { label: '10', station_no: 10, hits: 7 },
        { label: '4', station_no: 4, hits: 3 },
      ],
      total: 10,
    },
    {
      entry_row: 16,
      name_key: 'hadley ike',
      shooter_id: 3,
      display_name: 'Hadley, Ike',
      round_id: null,
      hits: [{ label: '4', station_no: 4, hits: 2 }],
      total: 2,
    },
    {
      entry_row: 17,
      name_key: 'hadley dik',
      shooter_id: null,
      display_name: null,
      round_id: null,
      hits: [
        { label: '4', station_no: 4, hits: 6 },
        { label: '10', station_no: 10, hits: 8 },
      ],
      total: 14,
    },
  ],
};

// The recorded score comes from the result the entry is linked to (round_id); only round_id and score are read.
const results = [
  { round_id: 7444, score: 12 },
  { round_id: 7450, score: 8 },
];

describe('stationMatrixModel', () => {
  it('builds one table row per sheet entry with station columns, total and the linked round score', () => {
    const model = stationMatrixModel(matrix, results);
    expect(model.columns).toEqual([
      { key: 'shooter', label: 'Shooter', type: 'string' },
      { key: 's4', label: 'Stn 4 (7)', type: 'int' },
      { key: 's10', label: 'Stn 10 (8)', type: 'int' },
      { key: 'total', label: 'Station total', type: 'int' },
      { key: 'score', label: 'Score', type: 'int' },
    ]);
    expect(model.rows).toEqual([
      { shooter: 'Nordquist, Sherman', s4: 5, s10: 7, total: 12, score: 12 },
      { shooter: 'Hadley, Ike', s4: 3, s10: 7, total: 10, score: 8 },
      { shooter: 'Hadley, Ike (2)', s4: 2, s10: null, total: 2, score: null },
      { shooter: 'hadley dik', s4: 6, s10: 8, total: 14, score: null },
    ]);
    // The heatmap itself shows hits per shooter and station; targets, totals and scores are table-only.
    const option = model.option as { xAxis: { data: string[] }; yAxis: { data: string[] } };
    expect(option.xAxis.data).toEqual(['Stn 4', 'Stn 10']);
    expect(option.yAxis.data).toEqual([
      'Nordquist, Sherman',
      'Hadley, Ike',
      'Hadley, Ike (2)',
      'hadley dik',
    ]);
  });
});

describe('stationLongData', () => {
  it('emits one (shooter, station, hits) row per cell for the heatmap, unmatched names by name key', () => {
    expect(stationLongData(matrix).rows).toEqual([
      { shooter: 'Nordquist, Sherman', station: 'Stn 4', hits: 5 },
      { shooter: 'Nordquist, Sherman', station: 'Stn 10', hits: 7 },
      { shooter: 'Hadley, Ike', station: 'Stn 4', hits: 3 },
      { shooter: 'Hadley, Ike', station: 'Stn 10', hits: 7 },
      { shooter: 'Hadley, Ike (2)', station: 'Stn 4', hits: 2 },
      { shooter: 'Hadley, Ike (2)', station: 'Stn 10', hits: null },
      { shooter: 'hadley dik', station: 'Stn 4', hits: 6 },
      { shooter: 'hadley dik', station: 'Stn 10', hits: 8 },
    ]);
  });
});

describe('a lettered station', () => {
  const lettered: StationMatrix = {
    layout: [
      { label: '7', station_no: 7, target_count: 8 },
      { label: '7A', station_no: 7, target_count: 6 },
      { label: '8', station_no: 8, target_count: 7 },
    ],
    entries: [
      {
        entry_row: 10,
        name_key: 'nordquist sherman',
        shooter_id: 12,
        display_name: 'Nordquist, Sherman',
        round_id: null,
        hits: [
          { label: '8', station_no: 8, hits: 5 },
          { label: '7A', station_no: 7, hits: 4 },
          { label: '7', station_no: 7, hits: 6 },
        ],
        total: 15,
      },
    ],
  };

  it('is its own column, after 7, with its own hits', () => {
    const model = stationMatrixModel(lettered, []);
    expect(model.columns.map((c) => c.label)).toEqual([
      'Shooter',
      'Stn 7 (8)',
      'Stn 7A (6)',
      'Stn 8 (7)',
      'Station total',
      'Score',
    ]);
    expect(model.rows).toEqual([
      { shooter: 'Nordquist, Sherman', s7: 6, s7A: 4, s8: 5, total: 15, score: null },
    ]);
    const option = model.option as { xAxis: { data: string[] } };
    expect(option.xAxis.data).toEqual(['Stn 7', 'Stn 7A', 'Stn 8']);
  });
});
