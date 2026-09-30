import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { shooterMatches } from '../mocks';
import { ShooterPicker } from './ShooterPicker';

describe('ShooterPicker', () => {
  it('searches after two characters and returns the chosen shooter', async () => {
    const seen: string[] = [];
    server.use(
      http.get('*/api/shooters', ({ request }) => {
        seen.push(String(new URL(request.url).searchParams.get('q')));
        return HttpResponse.json(shooterMatches);
      }),
    );
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<ShooterPicker label="Merge into" value={null} onChange={onChange} />);
    const box = screen.getByRole('searchbox', { name: 'Merge into' });
    await user.type(box, 'c');
    expect(screen.queryByRole('list', { name: 'Merge into matches' })).not.toBeInTheDocument();
    await user.type(box, 'r');
    await user.click(await screen.findByRole('button', { name: 'Hadley, Ike · 267 rounds' }));
    expect(onChange).toHaveBeenCalledWith({ shooter_id: 3, display_name: 'Hadley, Ike' });
    expect(seen).toEqual(['cr']);
  });

  it('shows the chosen shooter with a Change button that clears it', async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <ShooterPicker
        label="Shooter"
        value={{ shooter_id: 3, display_name: 'Hadley, Ike' }}
        onChange={onChange}
      />,
    );
    expect(screen.getByText('Hadley, Ike')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Change' }));
    expect(onChange).toHaveBeenCalledWith(null);
  });

  it('says when nothing matches', async () => {
    server.use(http.get('*/api/shooters', () => HttpResponse.json([])));
    const user = userEvent.setup();
    renderWithProviders(<ShooterPicker label="Shooter" value={null} onChange={vi.fn()} />);
    await user.type(screen.getByRole('searchbox', { name: 'Shooter' }), 'zz');
    expect(await screen.findByText('No shooters match')).toBeInTheDocument();
  });

  it('shows a search failure', async () => {
    server.use(
      http.get('*/api/shooters', () =>
        HttpResponse.json(
          { error: { code: 'internal', message: 'Internal server error' } },
          { status: 500 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<ShooterPicker label="Shooter" value={null} onChange={vi.fn()} />);
    await user.type(screen.getByRole('searchbox', { name: 'Shooter' }), 'zz');
    expect(await screen.findByRole('alert')).toHaveTextContent('Internal server error');
  });
});
