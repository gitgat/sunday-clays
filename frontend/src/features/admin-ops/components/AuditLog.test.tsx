import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { auditEntries } from '../mocks';
import { AuditLog, detailsSummary } from './AuditLog';

describe('detailsSummary', () => {
  it('lists primitive values and JSON-encodes nested ones', () => {
    expect(detailsSummary({ rule_id: 1, payload: { name_key: 'hadley dik', shooter_id: 3 } })).toBe(
      'rule_id=1, payload={"name_key":"hadley dik","shooter_id":3}',
    );
  });
});

describe('AuditLog', () => {
  it('lists admin actions newest first with role, action, IP and details', async () => {
    server.use(http.get('*/api/admin/audit', () => HttpResponse.json(auditEntries)));
    renderWithProviders(<AuditLog />);
    const rows = within(await screen.findByRole('table', { name: 'Audit log' }))
      .getAllByRole('row')
      .slice(1);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent('rules.create');
    expect(rows[0]).toHaveTextContent('—');
    expect(rows[1]).toHaveTextContent('imports.commit');
    expect(rows[1]).toHaveTextContent('203.0.113.7');
    expect(rows[1]).toHaveTextContent('import_id=1, confirm_removals=false, job_id=11');
  });

  it('says when nothing has been done yet', async () => {
    server.use(http.get('*/api/admin/audit', () => HttpResponse.json([])));
    renderWithProviders(<AuditLog />);
    expect(await screen.findByText('No admin actions yet.')).toBeInTheDocument();
  });

  it('shows a load failure', async () => {
    server.use(
      http.get('*/api/admin/audit', () =>
        HttpResponse.json(
          { error: { code: 'internal', message: 'Internal server error' } },
          { status: 500 },
        ),
      ),
    );
    renderWithProviders(<AuditLog />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Internal server error');
  });

  it('says it shows the latest entries and loads the next page on request', async () => {
    const page = (from: number, n: number) =>
      Array.from({ length: n }, (_, i) => ({ ...auditEntries[0], id: from - i }));
    const offsets: string[] = [];
    server.use(
      http.get('*/api/admin/audit', ({ request }) => {
        const url = new URL(request.url);
        offsets.push(`${url.searchParams.get('limit')}/${url.searchParams.get('offset')}`);
        return HttpResponse.json(
          url.searchParams.get('offset') === '0' ? page(300, 200) : page(100, 30),
        );
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<AuditLog />);
    expect(await screen.findByText('Showing the latest 200')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Load more' }));
    expect(await screen.findByText('Showing the latest 230')).toBeInTheDocument();
    expect(offsets).toEqual(['200/0', '200/200']);
    // A short page was the end of the log.
    expect(screen.queryByRole('button', { name: 'Load more' })).not.toBeInTheDocument();
    expect(screen.getAllByRole('row')).toHaveLength(231);
  });

  it('shows an entry once when a new row shifts the next page by one', async () => {
    const page = (from: number, n: number) =>
      Array.from({ length: n }, (_, i) => ({ ...auditEntries[0], id: from - i }));
    server.use(
      http.get('*/api/admin/audit', ({ request }) =>
        HttpResponse.json(
          new URL(request.url).searchParams.get('offset') === '0' ? page(300, 200) : page(101, 30),
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<AuditLog />);
    await user.click(await screen.findByRole('button', { name: 'Load more' }));
    expect(await screen.findByText('Showing the latest 229')).toBeInTheDocument();
    expect(screen.getAllByRole('row')).toHaveLength(230);
  });

  it('offers no "Load more" when the first page is not full', async () => {
    server.use(http.get('*/api/admin/audit', () => HttpResponse.json(auditEntries)));
    renderWithProviders(<AuditLog />);
    expect(await screen.findByText('Showing the latest 2')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Load more' })).not.toBeInTheDocument();
  });
});
