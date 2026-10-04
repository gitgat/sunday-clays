import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';
import * as share from '../../../lib/share';
import { specialSummary } from '../../events/mocks';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { regularRecap } from '../mocks';
import { RecapPage } from './RecapPage';

describe('RecapPage', () => {
  it('defaults to the latest held Sunday from the data and leaves ?date= unset', async () => {
    const { router } = renderWithProviders(<RecapPage />, { role: 'admin', route: '/admin/recap' });
    const box = await screen.findByRole('textbox', { name: 'Recap (plain text)' });
    expect((box as HTMLTextAreaElement).value).toMatch(/^Sunday Clays · Sunday, /);
    expect(router.state.location.search).toBe('');
    expect(screen.getByRole('combobox', { name: 'Sunday' })).toHaveValue(
      (screen.getAllByRole('option')[0] as HTMLOptionElement).value,
    );
  });

  it('switches to Markdown and copies it', async () => {
    const write = vi.fn().mockResolvedValue(undefined);
    const { user } = renderWithProviders(<RecapPage />, {
      role: 'admin',
      route: '/admin/recap?date=2026-09-27',
    });
    await user.click(await screen.findByRole('tab', { name: 'Markdown' }));
    // user-event installs its own clipboard on setup, so the spy goes in after the render
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: write },
      configurable: true,
    });
    await user.click(screen.getByRole('button', { name: 'Copy Markdown' }));
    expect(write.mock.calls[0]?.[0]).toMatch(/^\*\*Sunday Clays · /);
    expect(await screen.findByText('Copied.')).toBeInTheDocument();
  });

  it('falls back to selecting the text when the clipboard API fails', async () => {
    const exec = vi.fn().mockReturnValue(false);
    Object.defineProperty(document, 'execCommand', { value: exec, configurable: true });
    const { user } = renderWithProviders(<RecapPage />, {
      role: 'admin',
      route: '/admin/recap?date=2026-09-27',
    });
    const button = await screen.findByRole('button', { name: 'Copy text' });
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: vi.fn().mockRejectedValue(new Error('no')) },
      configurable: true,
    });
    await user.click(button);
    expect(exec).toHaveBeenCalledWith('copy');
    expect(
      await screen.findByText('Could not copy. Select the text and copy it by hand.'),
    ).toBeInTheDocument();
  });

  it('downloads the image card with the dated file name', async () => {
    const download = vi.spyOn(share, 'downloadElementAsImage').mockResolvedValue(undefined);
    const { user } = renderWithProviders(<RecapPage />, {
      role: 'admin',
      route: '/admin/recap?date=2026-09-27',
    });
    await user.click(await screen.findByRole('button', { name: 'Download image' }));
    expect(download.mock.calls[0]?.[1]).toBe('sunday-clays-recap-2026-09-27.png');
    expect(await screen.findByText('Image ready.')).toBeInTheDocument();
  });

  it('shows the badge while the switch is off', async () => {
    server.use(http.get('*/api/features', () => HttpResponse.json({ switches: {} })));
    renderWithProviders(<RecapPage />, { role: 'admin', route: '/admin/recap' });
    expect(await screen.findByText('Admin preview')).toBeInTheDocument();
  });

  it('shows a special shoot with its label in the list and in the text', async () => {
    server.use(
      http.get('*/api/events', () =>
        HttpResponse.json([{ ...specialSummary, results_complete: true }]),
      ),
    );
    renderWithProviders(<RecapPage />, { role: 'admin', route: '/admin/recap?date=2026-09-20' });
    const box = await screen.findByRole('textbox', { name: 'Recap (plain text)' });
    expect(screen.getAllByRole('option')[0]).toHaveTextContent('— 3-Bird Shoot');
    expect((box as HTMLTextAreaElement).value).toContain(
      '3-Bird Shoot (special shoot, 60 targets)',
    );
  });

  it('says so when the image cannot be made', async () => {
    vi.spyOn(share, 'downloadElementAsImage').mockRejectedValue(new Error('no'));
    const { user } = renderWithProviders(<RecapPage />, {
      role: 'admin',
      route: '/admin/recap?date=2026-09-27',
    });
    await user.click(await screen.findByRole('button', { name: 'Download image' }));
    expect(await screen.findByText('Could not create the image.')).toBeInTheDocument();
  });

  it('says so when the recap cannot be built', async () => {
    server.use(
      http.get('*/api/admin/recap/:date', () =>
        HttpResponse.json({ error: { code: 'recap_not_ready', message: 'no' } }, { status: 409 }),
      ),
    );
    renderWithProviders(<RecapPage />, { role: 'admin', route: '/admin/recap?date=2026-09-27' });
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not build the recap');
  });

  it('says so when no Sunday has full results yet', async () => {
    server.use(http.get('*/api/events', () => HttpResponse.json([])));
    renderWithProviders(<RecapPage />, { role: 'admin', route: '/admin/recap' });
    expect(await screen.findByText('No Sunday has full results yet.')).toBeInTheDocument();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(screen.queryByRole('combobox', { name: 'Sunday' })).not.toBeInTheDocument();
  });

  it('shows the loading status only while the Sundays are pending', async () => {
    server.use(http.get('*/api/events', () => new Promise<never>(() => undefined)));
    renderWithProviders(<RecapPage />, { role: 'admin', route: '/admin/recap' });
    expect(await screen.findByRole('status')).toHaveTextContent('Loading the recap');
  });

  it('shows an alert when the Sundays cannot be loaded', async () => {
    server.use(http.get('*/api/events', () => HttpResponse.json({}, { status: 500 })));
    renderWithProviders(<RecapPage />, { role: 'admin', route: '/admin/recap' });
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load the Sundays');
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('falls back to the latest held Sunday when ?date= is not one', async () => {
    const asked: string[] = [];
    server.use(
      http.get('*/api/admin/recap/:date', ({ params }) => {
        asked.push(String(params.date));
        return HttpResponse.json(regularRecap);
      }),
    );
    renderWithProviders(<RecapPage />, { role: 'admin', route: '/admin/recap?date=2000-01-02' });
    const box = await screen.findByRole('textbox', { name: 'Recap (plain text)' });
    const select = screen.getByRole('combobox', { name: 'Sunday' });
    expect(select).toHaveValue((screen.getAllByRole('option')[0] as HTMLOptionElement).value);
    expect((box as HTMLTextAreaElement).value).toMatch(/^Sunday Clays · /);
    expect((box as HTMLTextAreaElement).value).not.toContain('2000');
    expect(asked).not.toContain('2000-01-02');
    expect(asked).toContain((select as HTMLSelectElement).value);
  });

  it('ignores the round-type filter in the URL when listing Sundays', async () => {
    const seen: string[] = [];
    server.use(
      http.get('*/api/events', ({ request }) => {
        seen.push(new URL(request.url).search);
        return HttpResponse.json([{ ...specialSummary, results_complete: true }]);
      }),
    );
    renderWithProviders(<RecapPage />, { role: 'admin', route: '/admin/recap?rt=sporting' });
    await screen.findByRole('combobox', { name: 'Sunday' });
    expect(seen.length).toBeGreaterThan(0);
    expect(seen.every((q) => !q.includes('round_type'))).toBe(true);
  });

  it('clears the status line when the tab or the Sunday changes', async () => {
    const write = vi.fn().mockResolvedValue(undefined);
    const { user } = renderWithProviders(<RecapPage />, {
      role: 'admin',
      route: '/admin/recap?date=2026-09-27',
    });
    const button = await screen.findByRole('button', { name: 'Copy text' });
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: write },
      configurable: true,
    });
    await user.click(button);
    expect(await screen.findByText('Copied.')).toBeInTheDocument();
    await user.click(screen.getByRole('tab', { name: 'Markdown' }));
    expect(screen.queryByText('Copied.')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Copy Markdown' }));
    expect(await screen.findByText('Copied.')).toBeInTheDocument();
    const select = screen.getByRole('combobox', { name: 'Sunday' });
    const other = (screen.getAllByRole('option') as HTMLOptionElement[]).find(
      (o) => o.value !== (select as HTMLSelectElement).value,
    );
    await user.selectOptions(select, other?.value ?? '');
    expect(screen.queryByText('Copied.')).not.toBeInTheDocument();
  });

  it('captures the image from a fixed 600 px card, not the phone-width preview', async () => {
    const download = vi.spyOn(share, 'downloadElementAsImage').mockResolvedValue(undefined);
    const { user } = renderWithProviders(<RecapPage />, {
      role: 'admin',
      route: '/admin/recap?date=2026-09-27',
    });
    await user.click(await screen.findByRole('button', { name: 'Download image' }));
    const el = download.mock.calls[0]?.[0];
    expect(el?.className).toContain('w-[600px]');
    expect(el?.className).not.toContain('max-w-full');
    expect(el?.closest('[aria-hidden="true"]')).not.toBeNull();
  });

  it('lists a special shoot without a label by its date alone', async () => {
    server.use(
      http.get('*/api/events', () =>
        HttpResponse.json([{ ...specialSummary, label: null, results_complete: true }]),
      ),
    );
    renderWithProviders(<RecapPage />, { role: 'admin', route: '/admin/recap' });
    const option = (await screen.findAllByRole('option'))[0];
    expect(option?.textContent).not.toContain('—');
  });
});
