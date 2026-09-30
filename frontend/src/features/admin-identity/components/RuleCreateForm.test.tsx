import { fireEvent, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { UserEvent } from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { doneJob, shooterMatches } from '../../admin/mocks';
import { pickerEvent } from '../mocks';
import { RuleCreateForm } from './RuleCreateForm';

const created: unknown[] = [];

async function pick(user: UserEvent, label: string, match: string) {
  await user.type(screen.getByRole('searchbox', { name: label }), 'cr');
  await user.click(await screen.findByRole('button', { name: match }));
}

async function chooseType(user: UserEvent, type: string) {
  await user.selectOptions(screen.getByLabelText('Rule type'), type);
}

async function create(user: UserEvent) {
  await user.click(screen.getByRole('button', { name: 'Create rule' }));
  expect(await screen.findByText('Rule #3: Done')).toBeInTheDocument();
}

describe('RuleCreateForm', () => {
  beforeEach(() => {
    created.length = 0;
    server.use(
      http.get('*/api/shooters', () => HttpResponse.json(shooterMatches)),
      http.get('*/api/events/:date', () => HttpResponse.json(pickerEvent)),
      http.post('*/api/admin/rules', async ({ request }) => {
        created.push(await request.json());
        return HttpResponse.json({ rule_id: 3, job_id: 63 });
      }),
      http.get('*/api/admin/jobs/:id', ({ params }) =>
        HttpResponse.json({ ...doneJob, id: Number(params.id) }),
      ),
    );
  });

  it('offers the eight rule types and keeps Create disabled until the form is complete', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RuleCreateForm />);
    expect(screen.getByLabelText('Rule type').querySelectorAll('option')).toHaveLength(8);
    expect(screen.getByRole('button', { name: 'Create rule' })).toBeDisabled();
    await pick(user, 'Merge this shooter', 'Crimson, Al · 1 rounds');
    expect(screen.getByRole('button', { name: 'Create rule' })).toBeDisabled();
  });

  it('merge_shooter', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RuleCreateForm />);
    await pick(user, 'Merge this shooter', 'Crimson, Al · 1 rounds');
    await pick(user, 'Into this shooter', 'Hadley, Ike · 267 rounds');
    await create(user);
    expect(created).toEqual([
      {
        rule_type: 'merge_shooter',
        payload: { source_shooter_id: 90, target_shooter_id: 3 },
        note: null,
      },
    ]);
  });

  it('rename_shooter, with a note', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RuleCreateForm />);
    await chooseType(user, 'rename_shooter');
    await pick(user, 'Shooter', 'Hadley, Ike · 267 rounds');
    await user.type(screen.getByLabelText('New display name'), 'Hadley, Clint');
    await user.type(screen.getByLabelText('Note (optional)'), 'Prefers Clint');
    await create(user);
    expect(created).toEqual([
      {
        rule_type: 'rename_shooter',
        payload: { shooter_id: 3, display_name: 'Hadley, Clint' },
        note: 'Prefers Clint',
      },
    ]);
  });

  it('score_override picks a round from the event results', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RuleCreateForm />);
    await chooseType(user, 'score_override');
    fireEvent.change(screen.getByLabelText('Event date'), { target: { value: '2026-09-13' } });
    await user.click(await screen.findByRole('radio', { name: 'Hadley, Ike — 34' }));
    await user.type(screen.getByLabelText('Corrected score'), '36');
    await create(user);
    expect(created).toEqual([
      {
        rule_type: 'score_override',
        payload: { event_date: '2026-09-13', name_key: 'hadley ike', ordinal: 1, score: 36 },
        note: null,
      },
    ]);
  });

  it('hide_round picks a round from the event results', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RuleCreateForm />);
    await chooseType(user, 'hide_round');
    fireEvent.change(screen.getByLabelText('Event date'), { target: { value: '2026-09-13' } });
    await user.click(await screen.findByRole('radio', { name: 'Nickerson, Neal — 34 (round 2)' }));
    await create(user);
    expect(created).toEqual([
      {
        rule_type: 'hide_round',
        payload: { event_date: '2026-09-13', name_key: 'nickerson neal', ordinal: 2 },
        note: null,
      },
    ]);
  });

  it('round_type_override takes a date and a round type', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RuleCreateForm />);
    await chooseType(user, 'round_type_override');
    fireEvent.change(screen.getByLabelText('Event date'), { target: { value: '2026-09-27' } });
    await user.selectOptions(screen.getByLabelText('Round type'), 'sporting');
    await create(user);
    expect(created).toEqual([
      {
        rule_type: 'round_type_override',
        payload: { event_date: '2026-09-27', round_type: 'sporting' },
        note: null,
      },
    ]);
  });

  it('set_status takes a shooter and a status', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RuleCreateForm />);
    await chooseType(user, 'set_status');
    await pick(user, 'Shooter', 'Hadley, Ike · 267 rounds');
    await user.selectOptions(screen.getByLabelText('Status'), 'member');
    await create(user);
    expect(created).toEqual([
      { rule_type: 'set_status', payload: { shooter_id: 3, status: 'member' }, note: null },
    ]);
  });

  it('station_reset takes a station, an effective date and what changed', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RuleCreateForm />);
    await chooseType(user, 'station_reset');
    await user.type(screen.getByLabelText('Station (like 7 or 7A)'), '7a');
    fireEvent.change(screen.getByLabelText('Effective date'), { target: { value: '2026-10-04' } });
    await user.type(screen.getByLabelText('What changed'), 'New presentation on station 7A');
    await create(user);
    expect(created).toEqual([
      {
        rule_type: 'station_reset',
        payload: {
          station: '7A',
          effective_date: '2026-10-04',
          note: 'New presentation on station 7A',
        },
        note: null,
      },
    ]);
  });

  it('alias_name takes a name key and a shooter', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RuleCreateForm />);
    await chooseType(user, 'alias_name');
    await user.type(screen.getByLabelText('Name key'), 'hadley dik');
    await pick(user, 'Belongs to', 'Hadley, Ike · 267 rounds');
    await create(user);
    expect(created).toEqual([
      { rule_type: 'alias_name', payload: { name_key: 'hadley dik', shooter_id: 3 }, note: null },
    ]);
  });

  it('changing the type clears the previous fields', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RuleCreateForm />);
    await chooseType(user, 'alias_name');
    await user.type(screen.getByLabelText('Name key'), 'hadley dik');
    await chooseType(user, 'set_status');
    await chooseType(user, 'alias_name');
    expect(screen.getByLabelText('Name key')).toHaveValue('');
  });

  it('clears the fields and the note after a rule is created, so a second click cannot duplicate it', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RuleCreateForm />);
    await chooseType(user, 'alias_name');
    await user.type(screen.getByLabelText('Name key'), 'hadley dik');
    await pick(user, 'Belongs to', 'Hadley, Ike · 267 rounds');
    await user.type(screen.getByLabelText('Note (optional)'), 'typo');
    await create(user);
    expect(screen.getByLabelText('Name key')).toHaveValue('');
    expect(screen.getByLabelText('Note (optional)')).toHaveValue('');
    expect(screen.getByRole('button', { name: 'Create rule' })).toBeDisabled();
    expect(created).toHaveLength(1);
  });

  it('clears the note when the type changes', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RuleCreateForm />);
    await user.type(screen.getByLabelText('Note (optional)'), 'typo');
    await chooseType(user, 'set_status');
    expect(screen.getByLabelText('Note (optional)')).toHaveValue('');
  });

  it('shows a rejected rule next to the form', async () => {
    server.use(
      http.post('*/api/admin/rules', () =>
        HttpResponse.json(
          { error: { code: 'invalid_payload', message: 'Unknown shooter 3' } },
          { status: 400 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<RuleCreateForm />);
    await chooseType(user, 'alias_name');
    await user.type(screen.getByLabelText('Name key'), 'hadley dik');
    await pick(user, 'Belongs to', 'Hadley, Ike · 267 rounds');
    await user.click(screen.getByRole('button', { name: 'Create rule' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Unknown shooter 3');
  });
});
