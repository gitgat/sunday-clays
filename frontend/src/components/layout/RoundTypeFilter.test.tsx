import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../test/render';
import { RoundTypeFilter } from './RoundTypeFilter';

function setup(route = '/') {
  return renderWithProviders(
    <>
      <RoundTypeFilter />
      <p>outside</p>
    </>,
    { route },
  );
}

describe('RoundTypeFilter', () => {
  it('shows no Filtered chip while no round type is selected', () => {
    setup();
    expect(screen.queryByText(/Filtered:/)).toBeNull();
  });

  it('writes the selection to ?rt= and shows the Filtered chip', async () => {
    const { user, router } = setup();
    await user.click(screen.getByRole('button', { name: 'Round type' }));
    await user.click(screen.getByRole('checkbox', { name: 'Sporting' }));
    expect(router.state.location.search).toBe('?rt=sporting');
    expect(screen.getByText('Filtered: Sporting')).toBeInTheDocument();
    await user.click(screen.getByRole('checkbox', { name: 'Sporting' }));
    expect(router.state.location.search).toBe('');
    await user.click(screen.getByRole('checkbox', { name: 'Super Sporting' }));
    expect(router.state.location.search).toBe('?rt=super_sporting');
    expect(screen.getByText('Filtered: Super Sporting')).toBeInTheDocument();
  });

  it('offers exactly Sporting and Super Sporting', async () => {
    const { user } = setup();
    await user.click(screen.getByRole('button', { name: 'Round type' }));
    expect(screen.getAllByRole('checkbox')).toHaveLength(2);
    expect(screen.getByRole('checkbox', { name: 'Sporting' })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: 'Super Sporting' })).toBeInTheDocument();
  });

  it('reads the filter from the URL and clears it from the chip', async () => {
    const { user, router } = setup('/?rt=super_sporting');
    expect(screen.getByText('Filtered: Super Sporting')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Clear round type filter' }));
    expect(router.state.location.search).toBe('');
    expect(screen.queryByText(/Filtered:/)).toBeNull();
  });

  it('shows no Filtered chip when the URL selects every round type', () => {
    setup('/?rt=sporting,super_sporting');
    expect(screen.queryByText(/Filtered:/)).toBeNull();
  });

  it('returns focus to the Round type button after clearing the filter from the chip', async () => {
    const { user } = setup('/?rt=sporting');
    await user.click(screen.getByRole('button', { name: 'Clear round type filter' }));
    expect(screen.getByRole('button', { name: 'Round type' })).toHaveFocus();
  });

  it('closes when keyboard focus leaves the filter', async () => {
    const { user } = renderWithProviders(
      <>
        <RoundTypeFilter />
        <button type="button">after</button>
      </>,
      { route: '/?rt=sporting' },
    );
    await user.click(screen.getByRole('button', { name: 'Round type' }));
    // Sporting, Super Sporting, then the chip's clear button: all still inside.
    await user.tab();
    await user.tab();
    await user.tab();
    expect(screen.getByRole('button', { name: 'Clear round type filter' })).toHaveFocus();
    expect(screen.getByRole('group', { name: 'Round types' })).toBeInTheDocument();
    await user.tab();
    expect(screen.getByRole('button', { name: 'after' })).toHaveFocus();
    expect(screen.queryByRole('group', { name: 'Round types' })).toBeNull();
  });

  it('treats selecting every round type as no filter', async () => {
    const { user, router } = setup('/?rt=sporting');
    await user.click(screen.getByRole('button', { name: 'Round type' }));
    await user.click(screen.getByRole('checkbox', { name: 'Super Sporting' }));
    expect(router.state.location.search).toBe('');
  });

  it('closes on Escape and on a click outside', async () => {
    const { user } = setup();
    const trigger = screen.getByRole('button', { name: 'Round type' });
    await user.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('group', { name: 'Round types' })).toBeNull();
    await user.click(trigger);
    await user.click(screen.getByRole('checkbox', { name: 'Sporting' }));
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('group', { name: 'Round types' })).toBeNull();
    await user.click(trigger);
    await user.click(screen.getByText('outside'));
    expect(screen.queryByRole('group', { name: 'Round types' })).toBeNull();
  });

  it('returns focus to the Round type button when Escape closes the panel from inside', async () => {
    const { user } = setup();
    const trigger = screen.getByRole('button', { name: 'Round type' });
    await user.click(trigger);
    await user.click(screen.getByRole('checkbox', { name: 'Sporting' }));
    expect(screen.getByRole('checkbox', { name: 'Sporting' })).toHaveFocus();
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('group', { name: 'Round types' })).toBeNull();
    expect(trigger).toHaveFocus();
  });

  it('hangs the panel from the left edge by default and from the right edge when asked', async () => {
    const { user, unmount } = setup();
    await user.click(screen.getByRole('button', { name: 'Round type' }));
    expect(screen.getByRole('group', { name: 'Round types' })).toHaveClass('left-0');
    unmount();
    const right = renderWithProviders(<RoundTypeFilter align="right" />);
    await right.user.click(screen.getByRole('button', { name: 'Round type' }));
    const panel = screen.getByRole('group', { name: 'Round types' });
    expect(panel).toHaveClass('right-0');
    expect(panel).not.toHaveClass('left-0');
  });

  it('lets the keyboard reach and toggle the checkboxes without closing the panel', async () => {
    const { user, router } = setup();
    await user.click(screen.getByRole('button', { name: 'Round type' }));
    await user.tab();
    expect(screen.getByRole('checkbox', { name: 'Sporting' })).toHaveFocus();
    await user.keyboard(' ');
    expect(router.state.location.search).toBe('?rt=sporting');
    expect(screen.getByRole('group', { name: 'Round types' })).toBeInTheDocument();
  });

  it('stays open for clicks inside the panel', async () => {
    const { user } = setup();
    await user.click(screen.getByRole('button', { name: 'Round type' }));
    await user.click(screen.getByRole('group', { name: 'Round types' }));
    expect(screen.getByRole('group', { name: 'Round types' })).toBeInTheDocument();
  });
});
