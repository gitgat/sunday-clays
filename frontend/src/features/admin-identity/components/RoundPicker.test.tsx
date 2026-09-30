import { fireEvent, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import type { EventResult } from '../api';
import { pickerEvent, pickerResults } from '../mocks';
import type { RoundRef } from '../rules';
import { RoundPicker } from './RoundPicker';

function Harness() {
  const [round, setRound] = useState<RoundRef | null>(null);
  return (
    <>
      <RoundPicker value={round} onChange={setRound} />
      <p>
        {round === null ? 'no round' : `${round.event_date} ${round.name_key} #${round.ordinal}`}
      </p>
    </>
  );
}

/** Serves a complete EventDetail with these results, or a 404 (the events endpoint belongs to features/events). */
function results(list: EventResult[] | 'error') {
  server.use(
    http.get('*/api/events/:date', ({ params }) =>
      list === 'error'
        ? HttpResponse.json(
            { error: { code: 'event_not_found', message: 'No event on that date' } },
            { status: 404 },
          )
        : HttpResponse.json({ ...pickerEvent, event_date: String(params.date), results: list }),
    ),
  );
}

describe('RoundPicker', () => {
  it('lists the rounds of the chosen date, best first, and returns the chosen round', async () => {
    results(pickerResults);
    const user = userEvent.setup();
    renderWithProviders(<Harness />);
    fireEvent.change(screen.getByLabelText('Event date'), { target: { value: '2026-09-13' } });
    const radios = await screen.findAllByRole('radio');
    expect(radios.map((r) => r.closest('label')?.textContent)).toEqual([
      'Nordquist, Sherman — 42',
      'Hadley, Ike — 34',
      'Nickerson, Neal — 34 (round 2)',
    ]);
    await user.click(screen.getByRole('radio', { name: 'Hadley, Ike — 34' }));
    expect(screen.getByText('2026-09-13 hadley ike #1')).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: 'Hadley, Ike — 34' })).toBeChecked();
  });

  it("orders one shooter's equal-scoring rounds by round number", async () => {
    const [, hadley] = pickerResults as [EventResult, EventResult, EventResult];
    results([{ ...hadley, round_id: 9002, ordinal: 2 }, hadley]);
    renderWithProviders(<Harness />);
    fireEvent.change(screen.getByLabelText('Event date'), { target: { value: '2026-09-13' } });
    const radios = await screen.findAllByRole('radio');
    expect(radios.map((r) => r.closest('label')?.textContent)).toEqual([
      'Hadley, Ike — 34',
      'Hadley, Ike — 34 (round 2)',
    ]);
  });

  it('clears the chosen round when the date changes', async () => {
    results(pickerResults);
    const user = userEvent.setup();
    renderWithProviders(<Harness />);
    fireEvent.change(screen.getByLabelText('Event date'), { target: { value: '2026-09-13' } });
    await user.click(await screen.findByRole('radio', { name: 'Hadley, Ike — 34' }));
    fireEvent.change(screen.getByLabelText('Event date'), { target: { value: '2026-09-06' } });
    expect(screen.getByText('no round')).toBeInTheDocument();
  });

  it('says when a date has no rounds, or no event', async () => {
    results([]);
    renderWithProviders(<Harness />);
    fireEvent.change(screen.getByLabelText('Event date'), { target: { value: '2026-09-20' } });
    expect(await screen.findByText('No rounds on this date.')).toBeInTheDocument();
    results('error');
    fireEvent.change(screen.getByLabelText('Event date'), { target: { value: '2026-09-21' } });
    expect(await screen.findByRole('alert')).toHaveTextContent('No event on that date');
  });
});
