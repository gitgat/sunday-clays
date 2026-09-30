import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { doneJob } from '../../admin/mocks';
import { rules } from '../mocks';
import { RulesList } from './RulesList';

describe('RulesList', () => {
  beforeEach(() => {
    server.use(
      http.get('*/api/admin/rules', () => HttpResponse.json(rules)),
      http.get('*/api/admin/jobs/:id', ({ params }) =>
        HttpResponse.json({ ...doneJob, id: Number(params.id) }),
      ),
    );
  });

  it('lists rules with their type, payload, note and state', async () => {
    const legacy = { ...rules[1], id: 9, rule_type: 'legacy_rule' };
    server.use(http.get('*/api/admin/rules', () => HttpResponse.json([...rules, legacy])));
    renderWithProviders(<RulesList />);
    const table = await screen.findByRole('table', { name: 'Rules' });
    expect(within(table).getByRole('row', { name: /#9/ })).toHaveTextContent('legacy_rule');
    const alias = within(table).getByRole('row', { name: /#1/ });
    expect(alias).toHaveTextContent('Alias a name to a shooter');
    expect(alias).toHaveTextContent('name_key=hadley dik, shooter_id=3');
    expect(alias).toHaveTextContent('Station typo');
    expect(alias).toHaveTextContent('Active');
    expect(within(table).getByRole('row', { name: /#2/ })).toHaveTextContent('Inactive');
    expect(
      within(within(table).getByRole('row', { name: /#2/ })).queryByRole('button'),
    ).not.toBeInTheDocument();
  });

  it('deactivates an active rule and follows the rebuild', async () => {
    const seen: string[] = [];
    server.use(
      http.post('*/api/admin/rules/:id/deactivate', ({ params }) => {
        seen.push(String(params.id));
        return HttpResponse.json({ rule_id: Number(params.id), job_id: 64 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<RulesList />);
    await user.click(await screen.findByRole('button', { name: 'Deactivate rule #1' }));
    expect(await screen.findByText('Deactivating rule #1: Done')).toBeInTheDocument();
    expect(seen).toEqual(['1']);
  });

  it('shows a rejected deactivation', async () => {
    server.use(
      http.post('*/api/admin/rules/:id/deactivate', () =>
        HttpResponse.json(
          { error: { code: 'conflict', message: 'Rule 1 is already inactive' } },
          { status: 409 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<RulesList />);
    await user.click(await screen.findByRole('button', { name: 'Deactivate rule #1' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Rule 1 is already inactive');
  });

  it('says when there are no rules', async () => {
    server.use(http.get('*/api/admin/rules', () => HttpResponse.json([])));
    renderWithProviders(<RulesList />);
    expect(await screen.findByText('No rules yet.')).toBeInTheDocument();
  });

  it('disables Deactivate while the request is in flight so a double click sends one POST', async () => {
    let posts = 0;
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.post('*/api/admin/rules/:id/deactivate', async ({ params }) => {
        posts += 1;
        await gate;
        return HttpResponse.json({ rule_id: Number(params.id), job_id: 64 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<RulesList />);
    const button = await screen.findByRole('button', { name: 'Deactivate rule #1' });
    await user.dblClick(button);
    expect(button).toBeDisabled();
    expect(posts).toBe(1);
    release();
    expect(await screen.findByText('Deactivating rule #1: Done')).toBeInTheDocument();
  });
});
