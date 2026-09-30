import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import { stalePreview } from '../mocks';
import { FindingsList, findingLocation, groupFindings } from './FindingsList';

describe('groupFindings', () => {
  it('separates excluded rows, station mismatches and the rest grouped by code, warnings first', () => {
    const groups = groupFindings(stalePreview.findings);
    expect(groups.excluded.map((f) => f.code)).toEqual(['score_missing']);
    expect(groups.station.map((f) => f.name)).toEqual(['Hadley, Ike']);
    expect(groups.other.map((g) => [g.code, g.severity, g.items.length])).toEqual([
      ['non_sunday_date', 'warning', 2],
      ['attendance_without_scores', 'info', 1],
    ]);
  });

  it('orders groups of the same severity by code', () => {
    const finding = (code: string, severity: 'info' | 'warning') => ({
      code,
      severity,
      message: code,
    });
    const groups = groupFindings([
      finding('head_count_mismatch', 'warning'),
      finding('attendance_without_scores', 'info'),
      finding('first_name_only', 'warning'),
      finding('duplicate_identical_rows', 'info'),
    ]);
    expect(groups.other.map((g) => g.code)).toEqual([
      'first_name_only',
      'head_count_mismatch',
      'attendance_without_scores',
      'duplicate_identical_rows',
    ]);
  });
});

describe('findingLocation', () => {
  it('joins the parts that are present', () => {
    const [missing, station] = stalePreview.findings;
    expect(findingLocation(missing as (typeof stalePreview.findings)[number])).toBe(
      'ALL SCORE DETAIL · row 88 · Mar 7, 2021 · Eastwood, Stanley',
    );
    expect(findingLocation(station as (typeof stalePreview.findings)[number])).toBe(
      'Sep 13, 2026 · Hadley, Ike',
    );
  });

  it('treats absent location fields like nulls', () => {
    // Plan 03's FindingOut defaults sheet/row/event_date/name to None, so the generated type marks them optional.
    const bare = {
      code: 'x',
      severity: 'info',
      message: 'm',
    } as (typeof stalePreview.findings)[number];
    expect(findingLocation(bare)).toBe('');
  });
});

describe('FindingsList', () => {
  it('renders the three sections with counts', () => {
    renderWithProviders(<FindingsList findings={stalePreview.findings} />);
    const excluded = screen.getByRole('region', { name: 'Will not be imported' });
    expect(within(excluded).getByText('Score Shot is blank')).toBeInTheDocument();
    const station = screen.getByRole('region', { name: 'Station vs score' });
    expect(within(station).getByText(/Hadley, Ike/)).toBeInTheDocument();
    expect(screen.getByText('non_sunday_date (2) · warning')).toBeInTheDocument();
    expect(screen.getByText('attendance_without_scores (1) · info')).toBeInTheDocument();
  });

  it('says when there are no findings', () => {
    renderWithProviders(<FindingsList findings={[]} />);
    expect(screen.getByText('No findings.')).toBeInTheDocument();
  });
});
