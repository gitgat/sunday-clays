import { screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { shareElementAsImage } from '../../../lib/share';
import { renderWithProviders } from '../../../test/render';
import { postFixture, trophyPost } from '../mocks';
import { PostShareCard } from './PostShareCard';
import { SharePostButton } from './SharePostButton';

vi.mock('../../../lib/share', () => ({ shareElementAsImage: vi.fn() }));

afterEach(() => {
  vi.mocked(shareElementAsImage).mockReset();
});

describe('SharePostButton', () => {
  it('renders the branded card off screen, shares it, then removes it', async () => {
    const shared: { text: string; filename: string }[] = [];
    vi.mocked(shareElementAsImage).mockImplementation((el, filename) => {
      shared.push({ text: el.textContent ?? '', filename });
      return Promise.resolve('downloaded');
    });
    const { user } = renderWithProviders(
      <SharePostButton post={postFixture()} date="2026-09-27" />,
    );
    await user.click(screen.getByRole('button', { name: 'Share image' }));
    await waitFor(() => expect(shared).toHaveLength(1));
    expect(shared[0]?.filename).toBe(
      'sunday-sheet-2026-09-27-new-personal-best-for-ike-hadley.png',
    );
    expect(shared[0]?.text).toContain('The Sunday Sheet · Sep 27, 2026');
    expect(shared[0]?.text).toContain('New personal best for Ike Hadley: 46.');
    await waitFor(() => expect(document.body.textContent).not.toContain('The Sunday Sheet ·'));
    expect(screen.getByRole('button', { name: 'Share image' })).toBeEnabled();
  });

  it('says so when the image cannot be made', async () => {
    vi.mocked(shareElementAsImage).mockRejectedValue(new Error('canvas'));
    const { user } = renderWithProviders(<SharePostButton post={trophyPost} date="2026-09-27" />);
    await user.click(screen.getByRole('button', { name: 'Share image' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not create the image.');
  });
});

describe('PostShareCard', () => {
  it('carries the masthead strip, the headline and the chart it links to', () => {
    renderWithProviders(<PostShareCard post={postFixture()} date="2026-09-27" />);
    expect(screen.getByText('The Sunday Sheet · Sep 27, 2026')).toBeInTheDocument();
    expect(screen.getByText('46').tagName).toBe('STRONG');
    expect(
      screen.getByText("📈 Ike Hadley's scores, with the personal-best line"),
    ).toBeInTheDocument();
  });

  it('carries the trophy art for a trophy post, and no chart line', () => {
    const { container } = renderWithProviders(
      <PostShareCard post={trophyPost} date="2026-09-27" />,
    );
    expect(container.querySelector('svg, img')).not.toBeNull();
    expect(screen.queryByText(/📈/)).toBeNull();
    expect(screen.queryByRole('link')).toBeNull();
  });
});
