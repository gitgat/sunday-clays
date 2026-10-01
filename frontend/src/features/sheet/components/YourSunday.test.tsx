import { screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { getMe, setMe } from '../../../lib/me';
import { renderWithProviders } from '../../../test/render';
import type { HomeWidget } from '../../home/widgets';
import { YourSunday } from './YourSunday';

const nextTrophy: HomeWidget = {
  id: 'next-trophy',
  order: 10,
  slot: 'me',
  Component: ({ meId }) => <p>next trophy for {meId}</p>,
};

afterEach(() => {
  localStorage.clear();
});

function renderSlot(meId: number | null, skipped = false) {
  const handlers = { onPicked: vi.fn(), onCleared: vi.fn(), onSkipped: vi.fn() };
  const view = renderWithProviders(
    <YourSunday meId={meId} skipped={skipped} widgets={[nextTrophy]} {...handlers} />,
  );
  return { ...view, ...handlers };
}

describe('YourSunday', () => {
  it('asks "Which one are you?" while no shooter is picked', () => {
    renderSlot(null);
    expect(screen.getByRole('region', { name: 'Which one are you?' })).toBeInTheDocument();
  });

  it('shows nothing once this browser skipped', () => {
    const { container } = renderSlot(null, true);
    expect(container).toBeEmptyDOMElement();
  });

  it('shows the panel and the next trophy for "me", and "Not me" forgets the pick', async () => {
    setMe(3);
    const { user, onCleared } = renderSlot(3);
    const panel = await screen.findByRole('region', { name: 'Your Sunday' });
    expect(await within(panel).findByText('next trophy for 3')).toBeInTheDocument();
    await user.click(within(panel).getByRole('button', { name: 'Not me' }));
    expect(getMe()).toBeNull();
    expect(onCleared).toHaveBeenCalledTimes(1);
  });
});
