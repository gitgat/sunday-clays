import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { renderWithProviders } from '../../test/render';
import { WidenWindow } from './WidenWindow';

describe('WidenWindow', () => {
  it('offers 12M and All, and a tap sets the time window', async () => {
    const { user, router } = renderWithProviders(<WidenWindow />, { route: '/?rt=sporting' });
    const group = screen.getByRole('group', { name: 'Widen the window' });
    expect(
      within(group)
        .getAllByRole('button')
        .map((b) => b.textContent),
    ).toEqual(['12M', 'All']);
    await user.click(within(group).getByRole('button', { name: 'All' }));
    expect(router.state.location.search).toBe('?rt=sporting&w=all');
  });

  it('leaves out the window already chosen', () => {
    renderWithProviders(<WidenWindow />, { route: '/?w=12m' });
    const group = screen.getByRole('group', { name: 'Widen the window' });
    expect(within(group).queryByRole('button', { name: '12M' })).toBeNull();
    expect(within(group).getByRole('button', { name: 'All' })).toBeVisible();
  });

  it('renders nothing from All time', () => {
    renderWithProviders(<WidenWindow />, { route: '/?w=all' });
    expect(screen.queryByRole('group')).toBeNull();
  });
});
