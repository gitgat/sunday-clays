import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import { clearMe, getMe, setMe } from '../../../lib/me';
import { renderWithProviders } from '../../../test/render';
import { MeButton } from './MeButton';

describe('MeButton', () => {
  beforeEach(() => {
    clearMe();
  });

  it("That's me remembers the shooter and a second press forgets them", async () => {
    const user = userEvent.setup();
    renderWithProviders(<MeButton shooterId={3} />);
    await user.click(screen.getByRole('button', { name: "That's me" }));
    expect(getMe()).toBe(3);
    const pressed = screen.getByRole('button', { name: 'This is you' });
    expect(pressed).toHaveAttribute('aria-pressed', 'true');
    await user.click(pressed);
    expect(getMe()).toBeNull();
    expect(screen.getByRole('button', { name: "That's me" })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  it('starts pressed when this shooter is already remembered', () => {
    setMe(3);
    renderWithProviders(<MeButton shooterId={3} />);
    expect(screen.getByRole('button', { name: 'This is you' })).toBeInTheDocument();
  });

  it('switches the remembered shooter to this one', async () => {
    setMe(7);
    const user = userEvent.setup();
    renderWithProviders(<MeButton shooterId={3} />);
    await user.click(screen.getByRole('button', { name: "That's me" }));
    expect(getMe()).toBe(3);
  });
});
