import { screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { shareElementAsImage } from '../../lib/share';
import { server } from '../../test/msw/server';
import { renderWithProviders } from '../../test/render';
import { eventDetail } from '../events/mocks';
import { hadleyDetail } from '../shooters/mocks';
import { eventSection } from './eventSection';
import { profileSection } from './profileSection';

vi.mock('../../lib/share', () => ({ shareElementAsImage: vi.fn() }));

// restoreMocks keeps a vi.fn()'s call history between tests; each test reads calls[0].
beforeEach(() => {
  vi.mocked(shareElementAsImage).mockReset();
});

const failed = () => HttpResponse.json({ error: { code: 'x', message: 'x' } }, { status: 500 });

describe('share sections', () => {
  it('shares the Sunday results card as sunday-clays-<date>.png', async () => {
    vi.mocked(shareElementAsImage).mockResolvedValue('downloaded');
    server.use(http.get('*/api/events/:date', () => HttpResponse.json(eventDetail)));
    const { user } = renderWithProviders(<eventSection.Component date="2026-09-13" />);
    const section = screen.getByRole('region', { name: 'Shareable results card' });
    await user.click(await within(section).findByRole('button', { name: 'Share image' }));
    expect(vi.mocked(shareElementAsImage).mock.calls[0]?.[1]).toBe('sunday-clays-2026-09-13.png');
    expect(eventSection).toMatchObject({ id: 'share', title: 'Share', order: 95 });
  });

  it('shares the profile card as sunday-clays-<name>.png, following the round-type filter', async () => {
    vi.mocked(shareElementAsImage).mockResolvedValue('downloaded');
    const urls: string[] = [];
    server.use(
      http.get('*/api/shooters/:id', ({ request }) => {
        urls.push(request.url);
        return HttpResponse.json(hadleyDetail);
      }),
    );
    const { user } = renderWithProviders(<profileSection.Component shooterId={3} />, {
      route: '/?rt=sporting',
    });
    const section = screen.getByRole('region', { name: 'Shareable profile card' });
    await user.click(await within(section).findByRole('button', { name: 'Share image' }));
    expect(vi.mocked(shareElementAsImage).mock.calls[0]?.[1]).toBe('sunday-clays-hadley-ike.png');
    expect(new URL(urls[0] ?? '').searchParams.getAll('round_type')).toEqual(['sporting']);
    expect(profileSection).toMatchObject({ id: 'share', title: 'Share', order: 95 });
  });

  it('reports failed loads', async () => {
    server.use(http.get('*/api/events/:date', failed), http.get('*/api/shooters/:id', failed));
    renderWithProviders(
      <>
        <eventSection.Component date="2026-09-13" />
        <profileSection.Component shooterId={3} />
      </>,
    );
    expect(await screen.findByText('Could not load this Sunday.')).toBeInTheDocument();
    expect(await screen.findByText('Could not load this shooter.')).toBeInTheDocument();
  });
});
