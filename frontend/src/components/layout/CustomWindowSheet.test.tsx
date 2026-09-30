import { fireEvent, screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { homeMeta } from '../../features/home/mocks';
import { server } from '../../test/msw/server';
import { renderWithProviders } from '../../test/render';
import { stubViewport } from '../../test/viewport';
import { CustomWindowSheet } from './CustomWindowSheet';

afterEach(() => {
  vi.restoreAllMocks();
});

function setup(route = '/', onClose = vi.fn()) {
  const view = renderWithProviders(<CustomWindowSheet open onClose={onClose} />, { route });
  return { ...view, onClose };
}

describe('CustomWindowSheet', () => {
  it('renders nothing while closed', () => {
    renderWithProviders(<CustomWindowSheet open={false} onClose={() => undefined} />);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('is a bottom sheet on a phone and a centred dialog on desktop', () => {
    stubViewport('mobile');
    const { unmount } = setup();
    expect(screen.getByRole('dialog', { name: 'Custom dates' }).className).toContain(
      'rounded-t-sheet',
    );
    unmount();
    vi.restoreAllMocks();
    stubViewport('desktop');
    setup();
    expect(screen.getByRole('dialog', { name: 'Custom dates' }).className).toContain(
      'rounded-sheet',
    );
    expect(screen.getByRole('dialog', { name: 'Custom dates' }).className).not.toContain(
      'rounded-t-sheet',
    );
  });

  it('has labelled 44 px date inputs and buttons, with the helper line', () => {
    setup();
    const dialog = screen.getByRole('dialog', { name: 'Custom dates' });
    for (const label of ['Start date', 'End date']) {
      const input = within(dialog).getByLabelText(label);
      expect(input).toHaveAttribute('type', 'date');
      expect(input.className).toContain('min-h-11');
      expect(input.className).toContain('w-full');
    }
    for (const name of ['Apply', 'Cancel']) {
      expect(within(dialog).getByRole('button', { name }).className).toContain('min-h-11');
    }
    expect(
      within(dialog).getByText(/Charts and stats that follow the time window use these dates\./),
    ).toBeVisible();
  });

  it('explains that presets count back from the latest scored Sunday, not today', async () => {
    setup();
    const dialog = screen.getByRole('dialog', { name: 'Custom dates' });
    expect(
      await within(dialog).findByText(
        /presets \(8W, 3M, 6M, 12M, YTD\) count back from the latest scored Sunday, Sep 27, 2026, not from today/,
      ),
    ).toBeVisible();
  });

  it('offers "Back to last 8 weeks" only while a custom window is active', async () => {
    const { user, router, onClose, unmount } = setup('/?w=2025-03-01..2025-09-28');
    const dialog = screen.getByRole('dialog', { name: 'Custom dates' });
    await user.click(within(dialog).getByRole('button', { name: 'Back to last 8 weeks' }));
    expect(router.state.location.search).not.toContain('..');
    expect(onClose).toHaveBeenCalled();
    unmount();
    setup('/?w=6m');
    expect(screen.queryByRole('button', { name: 'Back to last 8 weeks' })).toBeNull();
  });

  it('prefills the current range and limits the inputs to the scored dates', async () => {
    setup();
    const start = screen.getByLabelText('Start date');
    const end = screen.getByLabelText('End date');
    // Default 8W window anchored on the latest scored Sunday.
    expect(await screen.findByDisplayValue('2026-08-03')).toBe(start);
    expect(end).toHaveValue('2026-09-27');
    for (const input of [start, end]) {
      expect(input).toHaveAttribute('min', homeMeta.first_event_date);
      expect(input).toHaveAttribute('max', homeMeta.last_score_date);
    }
  });

  it('prefills an all-time window from the first Sunday', async () => {
    setup('/?w=all');
    expect(await screen.findByDisplayValue(homeMeta.first_event_date as string)).toBe(
      screen.getByLabelText('Start date'),
    );
  });

  it('starts empty, and cannot be applied, while nothing is known', async () => {
    server.use(
      http.get('*/api/meta', () =>
        HttpResponse.json({ ...homeMeta, first_event_date: null, last_score_date: null }),
      ),
    );
    setup();
    expect(screen.getByLabelText('Start date')).toHaveValue('');
    expect(screen.getByRole('button', { name: 'Apply' })).toBeDisabled();
  });

  it('applies the picked dates to ?w= and closes', async () => {
    const { user, router, onClose } = setup('/x?rt=sporting');
    await screen.findByDisplayValue('2026-08-03');
    fireEvent.change(screen.getByLabelText('Start date'), { target: { value: '2025-03-01' } });
    fireEvent.change(screen.getByLabelText('End date'), { target: { value: '2025-09-28' } });
    await user.click(screen.getByRole('button', { name: 'Apply' }));
    expect(router.state.location.search).toBe('?rt=sporting&w=2025-03-01..2025-09-28');
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('allows a one-day range', async () => {
    const { user, router } = setup();
    await screen.findByDisplayValue('2026-08-03');
    fireEvent.change(screen.getByLabelText('Start date'), { target: { value: '2026-09-27' } });
    await user.click(screen.getByRole('button', { name: 'Apply' }));
    expect(router.state.location.search).toBe('?w=2026-09-27..2026-09-27');
  });

  it('Cancel closes without touching the URL', async () => {
    const { user, router, onClose } = setup('/x?w=6m');
    await user.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(router.state.location.search).toBe('?w=6m');
  });

  it('warns about a reversed range and disables Apply', async () => {
    setup();
    await screen.findByDisplayValue('2026-08-03');
    fireEvent.change(screen.getByLabelText('Start date'), { target: { value: '2026-10-01' } });
    expect(screen.getByRole('alert')).toHaveTextContent(
      'The start date must be on or before the end date.',
    );
    expect(screen.getByRole('button', { name: 'Apply' })).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Start date'), { target: { value: '2026-09-01' } });
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.getByRole('button', { name: 'Apply' })).toBeEnabled();
  });

  it('cannot be applied with a cleared date', async () => {
    setup();
    await screen.findByDisplayValue('2026-08-03');
    fireEvent.change(screen.getByLabelText('End date'), { target: { value: '' } });
    expect(screen.getByRole('button', { name: 'Apply' })).toBeDisabled();
    expect(screen.queryByRole('alert')).toBeNull();
  });
});
