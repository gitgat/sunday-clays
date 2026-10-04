import { screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';
import * as share from '../../lib/share';
import { server } from '../../test/msw/server';
import { renderWithProviders } from '../../test/render';
import { summaryFixture } from './mocks';
import { profileSection } from './profileSection';

const { Component } = profileSection;

function seen(): URL[] {
  const urls: URL[] = [];
  server.use(
    http.get('*/api/shooters/:id/summary', ({ request }) => {
      urls.push(new URL(request.url));
      return HttpResponse.json(summaryFixture);
    }),
  );
  return urls;
}

describe('summary profile section', () => {
  it('is a bare section just above Share', () => {
    expect(profileSection).toMatchObject({
      id: 'summary',
      title: 'Summary card',
      order: 90,
      bare: true,
    });
  });

  it('asks for the window, shows the card and downloads it', async () => {
    const urls = seen();
    const download = vi.spyOn(share, 'downloadElementAsImage').mockResolvedValue(undefined);
    const { user } = renderWithProviders(<Component shooterId={3} />, {
      route: '/shooters/3?w=3m',
    });
    expect(await screen.findByRole('heading', { name: 'Summary card' })).toBeInTheDocument();
    expect(await screen.findByText('Hadley, Ike')).toBeInTheDocument();
    expect(screen.getByText('All round types · sundayclays.claysmasher.com')).toBeInTheDocument();
    expect(urls[0]?.searchParams.get('to')).toBe('2026-09-27');
    expect(urls[0]?.searchParams.has('from')).toBe(true);
    await user.click(screen.getByRole('button', { name: 'Download image' }));
    expect(download.mock.calls[0]?.[1]).toBe(
      'sunday-clays-hadley-ike-2026-06-28-to-2026-09-27.png',
    );
    expect(screen.getByRole('button', { name: 'Share image' })).toBeInTheDocument();
  });

  it('sends no from for the All window', async () => {
    const urls = seen();
    renderWithProviders(<Component shooterId={3} />, { route: '/shooters/3?w=all' });
    await screen.findByText('Hadley, Ike');
    expect(urls[0]?.searchParams.has('from')).toBe(false);
    // The explainer's scope tag shows the same window, so look inside the card itself.
    expect(
      within(screen.getByRole('article')).getByText('All time · through Sep 27, 2026'),
    ).toBeInTheDocument();
  });

  it('shows the empty window with 12M and All, and no image buttons', async () => {
    server.use(
      http.get('*/api/shooters/:id/summary', () =>
        HttpResponse.json({ ...summaryFixture, sundays: 0, special_sundays: 0, rounds: 0 }),
      ),
    );
    renderWithProviders(<Component shooterId={3} />, { route: '/shooters/3' });
    expect(await screen.findByText('No Sundays shot in this window.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Show all time' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Download image' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Share image' })).not.toBeInTheDocument();
  });

  it('says so when the summary cannot be loaded', async () => {
    server.use(
      http.get('*/api/shooters/:id/summary', () => HttpResponse.json({}, { status: 500 })),
    );
    renderWithProviders(<Component shooterId={3} />, { route: '/shooters/3?w=3m' });
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load the summary.');
  });

  it('shows a loading line, then says when the image could not be made', async () => {
    seen();
    vi.spyOn(share, 'downloadElementAsImage').mockRejectedValue(new Error('no canvas'));
    const { user } = renderWithProviders(<Component shooterId={3} />, {
      route: '/shooters/3?w=3m',
    });
    expect(await screen.findByRole('status')).toHaveTextContent('Loading the summary…');
    await user.click(await screen.findByRole('button', { name: 'Download image' }));
    expect(await screen.findByText('Could not create the image.')).toBeInTheDocument();
    vi.spyOn(share, 'downloadElementAsImage').mockResolvedValue(undefined);
    await user.click(screen.getByRole('button', { name: 'Download image' }));
    await waitFor(() => {
      expect(screen.queryByText('Could not create the image.')).not.toBeInTheDocument();
    });
  });

  it('disables Download image while the image is being made, so a double tap saves once', async () => {
    seen();
    let finish: () => void = () => undefined;
    const download = vi.spyOn(share, 'downloadElementAsImage').mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          finish = resolve;
        }),
    );
    const { user } = renderWithProviders(<Component shooterId={3} />, {
      route: '/shooters/3?w=3m',
    });
    const button = await screen.findByRole('button', { name: 'Download image' });
    await user.dblClick(button);
    expect(download).toHaveBeenCalledTimes(1);
    expect(button).toBeDisabled();
    finish();
    await waitFor(() => {
      expect(button).toBeEnabled();
    });
  });

  it('names the card by the shooter heading', async () => {
    seen();
    renderWithProviders(<Component shooterId={3} />, { route: '/shooters/3?w=3m' });
    expect(await screen.findByRole('article', { name: 'Hadley, Ike' })).toBeInTheDocument();
  });

  it('renders nothing at all (no heading) for a viewer while off', async () => {
    server.use(http.get('*/api/features', () => HttpResponse.json({ switches: {} })));
    const { container } = renderWithProviders(<Component shooterId={3} />);
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(container).toBeEmptyDOMElement();
  });
});
