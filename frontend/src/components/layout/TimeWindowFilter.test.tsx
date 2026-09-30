import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { stubViewport } from '../../test/viewport';
import { renderWithProviders } from '../../test/render';
import { TimeWindowFilter } from './TimeWindowFilter';

describe('TimeWindowFilter', () => {
  it('offers 8W, 3M, 6M, 12M, YTD, All and Custom, with the default pressed', () => {
    renderWithProviders(<TimeWindowFilter />);
    const group = screen.getByRole('group', { name: 'Time window' });
    const buttons = within(group).getAllByRole('button');
    expect(buttons.map((b) => b.textContent)).toEqual([
      '8W',
      '3M',
      '6M',
      '12M',
      'YTD',
      'All',
      'Custom',
    ]);
    expect(buttons.map((b) => b.getAttribute('aria-pressed'))).toEqual([
      'true',
      'false',
      'false',
      'false',
      'false',
      'false',
      'false',
    ]);
    for (const b of buttons) expect(b.className).toContain('min-h-11');
  });

  it('describes each window in full for assistive tech, keeping the short visible name', () => {
    renderWithProviders(<TimeWindowFilter />);
    expect(screen.getByRole('button', { name: '6M' })).toHaveAccessibleDescription('Last 6 months');
    expect(screen.getByRole('button', { name: '8W' })).toHaveAccessibleDescription('Last 8 weeks');
    expect(screen.getByRole('button', { name: 'YTD' })).toHaveAccessibleDescription(
      'This year to date',
    );
  });

  describe('as a select (the phone top bar)', () => {
    it('is one 44 px labelled select with short option labels, the default chosen', () => {
      renderWithProviders(<TimeWindowFilter variant="select" />);
      const select = screen.getByRole('combobox', { name: 'Time window' });
      expect(select.className).toContain('min-h-11');
      expect(
        within(select)
          .getAllByRole('option')
          .map((o) => o.textContent),
      ).toEqual(['8W', '3M', '6M', '12M', 'YTD', 'All', 'Custom…']);
      expect(select).toHaveValue('8w');
      expect(screen.queryByRole('group', { name: 'Time window' })).toBeNull();
    });

    it('keeps the full wording for assistive tech: a title and a description of the choice', async () => {
      const { user } = renderWithProviders(<TimeWindowFilter variant="select" />);
      const select = screen.getByRole('combobox', { name: 'Time window' });
      expect(select).toHaveAccessibleDescription('Last 8 weeks');
      expect(select).toHaveAttribute('title', 'Last 8 weeks');
      await user.selectOptions(select, 'ytd');
      expect(select).toHaveAccessibleDescription('This year to date');
      expect(select).toHaveAttribute('title', 'This year to date');
      expect(within(select).getByRole('option', { name: 'Last 12 months' })).toHaveTextContent(
        '12M',
      );
    });

    it('writes a non-default window to ?w= and clears it for the default', async () => {
      const { user, router } = renderWithProviders(<TimeWindowFilter variant="select" />, {
        route: '/?rt=sporting',
      });
      const select = screen.getByRole('combobox', { name: 'Time window' });
      await user.selectOptions(select, '6m');
      expect(router.state.location.search).toBe('?rt=sporting&w=6m');
      expect(select).toHaveValue('6m');
      await user.selectOptions(select, '8w');
      expect(router.state.location.search).toBe('?rt=sporting');
    });
  });

  it('writes a non-default window to ?w= and clears it for the default', async () => {
    const { user, router } = renderWithProviders(<TimeWindowFilter />);
    await user.click(screen.getByRole('button', { name: '6M' }));
    expect(router.state.location.search).toBe('?w=6m');
    expect(screen.getByRole('button', { name: '6M' })).toHaveAttribute('aria-pressed', 'true');
    await user.click(screen.getByRole('button', { name: '8W' }));
    expect(router.state.location.search).toBe('');
  });

  it('keeps other query parameters and reads the window from the URL', async () => {
    const { user, router } = renderWithProviders(<TimeWindowFilter />, {
      route: '/?rt=sporting&w=all',
    });
    expect(screen.getByRole('button', { name: 'All' })).toHaveAttribute('aria-pressed', 'true');
    await user.click(screen.getByRole('button', { name: 'YTD' }));
    expect(router.state.location.search).toBe('?rt=sporting&w=ytd');
  });

  it('treats a retired ?w=season link as the default 8W', () => {
    renderWithProviders(<TimeWindowFilter />, { route: '/?w=season' });
    expect(screen.getByRole('button', { name: '8W' })).toHaveAttribute('aria-pressed', 'true');
  });

  describe('Custom dates', () => {
    const CUSTOM = '2025-03-01..2025-09-28';

    it('marks Custom as opening a dialog, pressed only for a custom window, described by the dates', () => {
      const { unmount } = renderWithProviders(<TimeWindowFilter />);
      const custom = screen.getByRole('button', { name: 'Custom' });
      expect(custom).toHaveAttribute('aria-haspopup', 'dialog');
      expect(custom).toHaveAttribute('aria-pressed', 'false');
      expect(custom).toHaveAccessibleDescription('Pick your own start and end dates');
      unmount();
      renderWithProviders(<TimeWindowFilter />, { route: `/?w=${CUSTOM}` });
      const active = screen.getByRole('button', { name: 'Custom' });
      expect(active).toHaveAttribute('aria-pressed', 'true');
      expect(active).toHaveAccessibleDescription('Mar 1, 2025 – Sep 28, 2025');
      expect(screen.getByRole('button', { name: '8W' })).toHaveAttribute('aria-pressed', 'false');
    });

    it('opens the sheet, and Apply writes the range to ?w=', async () => {
      stubViewport('desktop');
      const { user, router } = renderWithProviders(<TimeWindowFilter />, {
        route: '/?rt=sporting',
      });
      await user.click(screen.getByRole('button', { name: 'Custom' }));
      const dialog = await screen.findByRole('dialog', { name: 'Custom dates' });
      await user.clear(within(dialog).getByLabelText('Start date'));
      await user.type(within(dialog).getByLabelText('Start date'), '2025-03-01');
      await user.clear(within(dialog).getByLabelText('End date'));
      await user.type(within(dialog).getByLabelText('End date'), '2025-09-28');
      await user.click(within(dialog).getByRole('button', { name: 'Apply' }));
      expect(router.state.location.search).toBe(`?rt=sporting&w=${CUSTOM}`);
      expect(screen.queryByRole('dialog')).toBeNull();
      expect(screen.getByRole('button', { name: 'Custom' })).toHaveAttribute(
        'aria-pressed',
        'true',
      );
    });

    it('opens again over a custom window to edit it, prefilled with its dates', async () => {
      const { user } = renderWithProviders(<TimeWindowFilter />, { route: `/?w=${CUSTOM}` });
      await user.click(screen.getByRole('button', { name: 'Custom' }));
      const dialog = await screen.findByRole('dialog', { name: 'Custom dates' });
      expect(within(dialog).getByLabelText('Start date')).toHaveValue('2025-03-01');
      expect(within(dialog).getByLabelText('End date')).toHaveValue('2025-09-28');
    });

    it('opens the select variant to the sheet and leaves the URL alone until Apply', async () => {
      const { user, router } = renderWithProviders(<TimeWindowFilter variant="select" />);
      const select = screen.getByRole('combobox', { name: 'Time window' });
      await user.selectOptions(select, 'custom');
      const dialog = await screen.findByRole('dialog', { name: 'Custom dates' });
      expect(router.state.location.search).toBe('');
      expect(select).toHaveValue('8w');
      await user.click(within(dialog).getByRole('button', { name: 'Cancel' }));
      expect(screen.queryByRole('dialog')).toBeNull();
      expect(router.state.location.search).toBe('');
    });

    it('shows Custom as chosen in the select, with an edit option only then', async () => {
      const { user } = renderWithProviders(<TimeWindowFilter variant="select" />, {
        route: `/?w=${CUSTOM}`,
      });
      const select = screen.getByRole('combobox', { name: 'Time window' });
      expect(select).toHaveValue('custom');
      expect(select).toHaveAttribute('title', 'Mar 1, 2025 – Sep 28, 2025');
      expect(select).toHaveAccessibleDescription('Mar 1, 2025 – Sep 28, 2025');
      expect(
        within(select)
          .getAllByRole('option')
          .map((o) => o.textContent),
      ).toEqual(['8W', '3M', '6M', '12M', 'YTD', 'All', 'Mar 1 – Sep 28', 'Change dates…']);
      await user.selectOptions(select, 'edit');
      expect(await screen.findByRole('dialog', { name: 'Custom dates' })).toBeVisible();
      expect(select).toHaveValue('custom');
    });

    it('shows the custom dates as the select text, where a phone has no hover', () => {
      renderWithProviders(<TimeWindowFilter variant="select" />, { route: `/?w=${CUSTOM}` });
      const select = screen.getByRole<HTMLSelectElement>('combobox', { name: 'Time window' });
      expect(select.selectedOptions[0]?.textContent).toBe('Mar 1 – Sep 28');
    });

    it('keeps a range across two years short enough for the phone top bar', () => {
      renderWithProviders(<TimeWindowFilter variant="select" />, {
        route: '/?w=2025-08-03..2026-09-27',
      });
      const select = screen.getByRole<HTMLSelectElement>('combobox', { name: 'Time window' });
      expect(select.selectedOptions[0]?.textContent).toBe("Aug '25 – Sep '26");
      // The full dates stay in the title and the accessible description.
      expect(select).toHaveAttribute('title', 'Aug 3, 2025 – Sep 27, 2026');
    });

    it('a preset chosen in the select replaces a custom window', async () => {
      const { user, router } = renderWithProviders(<TimeWindowFilter variant="select" />, {
        route: `/?w=${CUSTOM}`,
      });
      await user.selectOptions(screen.getByRole('combobox', { name: 'Time window' }), '6m');
      expect(router.state.location.search).toBe('?w=6m');
    });
  });
});
