import { screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { getMe, isMeSkipped } from '../../../lib/me';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { shooterList } from '../../shooters/mocks';
import { WhichOneAreYou } from './WhichOneAreYou';

afterEach(() => {
  localStorage.clear();
});

function searched() {
  const asked: (string | null)[] = [];
  server.use(
    http.get('*/api/shooters', ({ request }) => {
      const q = new URL(request.url).searchParams.get('q');
      asked.push(q);
      const hits = shooterList.filter((s) =>
        s.display_name.toLowerCase().includes((q ?? '').toLowerCase()),
      );
      return HttpResponse.json(hits);
    }),
  );
  return asked;
}

describe('WhichOneAreYou', () => {
  it('searches by name and remembers the pick', async () => {
    const asked = searched();
    const onPicked = vi.fn();
    const { user } = renderWithProviders(
      <WhichOneAreYou onPicked={onPicked} onSkipped={vi.fn()} />,
    );
    await user.type(screen.getByLabelText('Your name'), 'Hadley');
    const list = await screen.findByRole('list', { name: 'Matching shooters' });
    await user.click(within(list).getByRole('button', { name: 'Hadley, Ike' }));
    expect(getMe()).toBe(3);
    expect(onPicked).toHaveBeenCalledWith(3);
    expect(asked.at(-1)).toBe('Hadley');
  });

  it('does not search for a single letter', async () => {
    const asked = searched();
    const { user } = renderWithProviders(<WhichOneAreYou onPicked={vi.fn()} onSkipped={vi.fn()} />);
    await user.type(screen.getByLabelText('Your name'), 'H');
    expect(screen.queryByRole('list', { name: 'Matching shooters' })).toBeNull();
    expect(asked).toEqual([]);
  });

  it('says when no shooter matches', async () => {
    searched();
    const { user } = renderWithProviders(<WhichOneAreYou onPicked={vi.fn()} onSkipped={vi.fn()} />);
    await user.type(screen.getByLabelText('Your name'), 'Zz');
    expect(await screen.findByText('No shooter matches “Zz”.')).toBeInTheDocument();
  });

  it('says so when the search fails', async () => {
    server.use(
      http.get('*/api/shooters', () =>
        HttpResponse.json({ error: { code: 'internal', message: 'x' } }, { status: 500 }),
      ),
    );
    const { user } = renderWithProviders(<WhichOneAreYou onPicked={vi.fn()} onSkipped={vi.fn()} />);
    await user.type(screen.getByLabelText('Your name'), 'Hadley');
    expect(await screen.findByText('Couldn’t search the shooters just now.')).toBeInTheDocument();
  });

  it('skips for good on this browser', async () => {
    const onSkipped = vi.fn();
    const { user } = renderWithProviders(
      <WhichOneAreYou onPicked={vi.fn()} onSkipped={onSkipped} />,
    );
    await user.click(screen.getByRole('button', { name: 'Not a shooter / skip' }));
    expect(isMeSkipped()).toBe(true);
    expect(onSkipped).toHaveBeenCalledTimes(1);
    expect(getMe()).toBeNull();
  });
});
