import { screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import type { DataIssue } from '../api';
import { dataIssues } from '../mocks';
import { DataIssues, groupIssues } from './DataIssues';

const ruleError: DataIssue = {
  id: 9,
  code: 'rule_target_missing',
  severity: 'error',
  event_date: null,
  shooter_id: null,
  message: 'Rule 12 targets a round that no longer exists',
  details: { rule_id: 12 },
};

describe('groupIssues', () => {
  it('groups by code, errors first, then warnings, then info, codes alphabetical', () => {
    expect(
      groupIssues([...dataIssues, ruleError]).map((g) => [g.code, g.severity, g.items.length]),
    ).toEqual([
      ['rule_target_missing', 'error', 1],
      ['incomplete_results', 'warning', 1],
      ['station_name_unmatched', 'warning', 1],
      ['station_score_mismatch', 'warning', 1],
      ['merged_same_day_rounds', 'info', 1],
    ]);
  });
});

describe('DataIssues', () => {
  it('shows each group with its issues, links and the assign action for unmatched station names', async () => {
    server.use(http.get('*/api/admin/data-issues', () => HttpResponse.json(dataIssues)));
    renderWithProviders(<DataIssues />);
    expect(await screen.findByText('incomplete_results (1) · warning')).toBeInTheDocument();
    const mismatch = screen.getByText('Station total 36 vs score 34').closest('li') as HTMLElement;
    expect(within(mismatch).getByRole('link', { name: 'Sep 13, 2026' })).toHaveAttribute(
      'href',
      '/events/2026-09-13',
    );
    expect(within(mismatch).getByRole('link', { name: 'Shooter #3' })).toHaveAttribute(
      'href',
      '/shooters/3',
    );
    expect(
      within(mismatch).queryByRole('button', { name: 'Assign to shooter' }),
    ).not.toBeInTheDocument();
    const unmatched = screen
      .getByText('No shooter matches “Hadley, Dik”')
      .closest('li') as HTMLElement;
    expect(
      within(unmatched).getByRole('button', { name: 'Assign to shooter' }),
    ).toBeInTheDocument();
  });

  it('keeps the round-type filter on its links', async () => {
    server.use(http.get('*/api/admin/data-issues', () => HttpResponse.json(dataIssues)));
    renderWithProviders(<DataIssues />, { route: '/admin/ops?rt=sporting' });
    const mismatch = (await screen.findByText('Station total 36 vs score 34')).closest(
      'li',
    ) as HTMLElement;
    expect(within(mismatch).getByRole('link', { name: 'Sep 13, 2026' })).toHaveAttribute(
      'href',
      '/events/2026-09-13?rt=sporting',
    );
    expect(within(mismatch).getByRole('link', { name: 'Shooter #3' })).toHaveAttribute(
      'href',
      '/shooters/3?rt=sporting',
    );
  });

  it('falls back to the name key when an unmatched issue has no raw name', async () => {
    server.use(
      http.get('*/api/admin/data-issues', () =>
        HttpResponse.json([{ ...dataIssues[2], details: { name_key: 'hadley dik' } }]),
      ),
    );
    renderWithProviders(<DataIssues />);
    expect(await screen.findByText('station_name_unmatched (1) · warning')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Assign to shooter' })).toBeInTheDocument();
  });

  it('says when there are no data issues', async () => {
    server.use(http.get('*/api/admin/data-issues', () => HttpResponse.json([])));
    renderWithProviders(<DataIssues />);
    expect(await screen.findByText('No data issues.')).toBeInTheDocument();
  });

  it('shows a load failure', async () => {
    server.use(
      http.get('*/api/admin/data-issues', () =>
        HttpResponse.json(
          { error: { code: 'internal', message: 'Internal server error' } },
          { status: 500 },
        ),
      ),
    );
    renderWithProviders(<DataIssues />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Internal server error');
  });
});
