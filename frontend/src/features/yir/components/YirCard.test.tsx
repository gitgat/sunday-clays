import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { shareElementAsImage } from '../../../lib/share';
import { YirCard } from './YirCard';

vi.mock('../../../lib/share', () => ({ shareElementAsImage: vi.fn() }));

beforeEach(() => {
  vi.mocked(shareElementAsImage).mockReset();
});

const explainer = {
  what: 'What it is',
  read: ['How to read it'],
  computed: ['How it is worked out'],
};

describe('YirCard sharing', () => {
  it('shares the card as sunday-clays-<title>.png and keeps the explainer out of the image', async () => {
    vi.mocked(shareElementAsImage).mockResolvedValue('downloaded');
    const user = userEvent.setup();
    render(
      <YirCard title="2025 at a glance" explainer={explainer}>
        <p>1,267 rounds</p>
      </YirCard>,
    );
    await user.click(screen.getByRole('button', { name: 'About this card' }));
    await user.click(screen.getByRole('button', { name: 'Share image: 2025 at a glance' }));
    const [element, filename] = vi.mocked(shareElementAsImage).mock.calls[0] ?? [];
    expect(element).toHaveTextContent('1,267 rounds');
    expect(filename).toBe('sunday-clays-2025-at-a-glance.png');
    // The disclosure and its panel carry data-share-exclude, which lib/share.ts filters out.
    const excluded = (element as HTMLElement).querySelectorAll('[data-share-exclude]');
    expect(excluded).toHaveLength(2);
    expect(screen.getByRole('region', { name: '2025 at a glance' })).toHaveTextContent(
      '1,267 rounds',
    );
  });
});
