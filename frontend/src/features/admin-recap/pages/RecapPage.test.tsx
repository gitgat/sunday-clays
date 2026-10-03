import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';
import * as share from '../../../lib/share';
import { specialSummary } from '../../events/mocks';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { RecapPage } from './RecapPage';

describe('RecapPage', () => {
  it('defaults to the latest held Sunday from the data and keeps it in ?date=', async () => {
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
    renderWithProviders(<RecapPage />, { role: 'admin', route: '/admin/recap?date=2026-09-20' });
    const box = await screen.findByRole('textbox', { name: 'Recap (plain text)' });
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

  it('waits quietly when there is no Sunday with results to pick', async () => {
    server.use(http.get('*/api/events', () => HttpResponse.json([])));
    renderWithProviders(<RecapPage />, { role: 'admin', route: '/admin/recap' });
    expect(await screen.findByRole('status')).toHaveTextContent('Loading the recap');
    expect(screen.queryByRole('combobox', { name: 'Sunday' })).not.toBeInTheDocument();
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
