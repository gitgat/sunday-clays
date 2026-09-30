import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { shareElementAsImage } from '../../lib/share';
import { ShareCard } from './ShareCard';

// html-to-image and the Web Share API are the external boundary; lib/share.ts owns them.
vi.mock('../../lib/share', () => ({ shareElementAsImage: vi.fn() }));

// restoreMocks keeps a vi.fn()'s calls and implementation between tests.
beforeEach(() => {
  vi.mocked(shareElementAsImage).mockReset();
});

function renderCard() {
  render(
    <ShareCard filename="sunday-clays-2026-09-13.png" name="Sep 13">
      <p>Results card</p>
    </ShareCard>,
  );
  return screen.getByRole('button', { name: 'Share image: Sep 13' });
}

/** The polite live line beside the button (a plain aria-live span, not role=status, so pages that
 * wait for "no status left" are not held up by an empty one). */
function liveLine(): HTMLElement {
  const line = document.querySelector<HTMLElement>('[aria-live="polite"]');
  if (line === null) throw new Error('no live line');
  return line;
}

describe('ShareCard', () => {
  it('renders exactly the wrapped card under the given filename', async () => {
    vi.mocked(shareElementAsImage).mockResolvedValue('downloaded');
    await userEvent.setup().click(renderCard());
    expect(shareElementAsImage).toHaveBeenCalledTimes(1);
    const [element, filename] = vi.mocked(shareElementAsImage).mock.calls[0] ?? [];
    expect(element).toHaveTextContent('Results card');
    expect(element).not.toHaveTextContent('Share image');
    expect(filename).toBe('sunday-clays-2026-09-13.png');
    expect(await screen.findByText('Image ready.')).toBeInTheDocument();
  });

  it('stays quiet when the share sheet is dismissed', async () => {
    vi.mocked(shareElementAsImage).mockResolvedValue('cancelled');
    await userEvent.setup().click(renderCard());
    expect(liveLine()).toHaveTextContent('');
    expect(screen.getByRole('button', { name: /Share image/ })).toBeEnabled();
  });

  it('disables the button while the image is being made', async () => {
    let finish: (value: 'downloaded') => void = () => undefined;
    vi.mocked(shareElementAsImage).mockReturnValue(new Promise((resolve) => (finish = resolve)));
    const button = renderCard();
    await userEvent.setup().click(button);
    expect(button).toBeDisabled();
    expect(liveLine()).toHaveTextContent('Preparing image…');
    finish('downloaded');
    expect(await screen.findByText('Image ready.')).toBeInTheDocument();
  });

  it('says when the image could not be made', async () => {
    vi.mocked(shareElementAsImage).mockRejectedValue(new Error('canvas tainted'));
    await userEvent.setup().click(renderCard());
    expect(await screen.findByText('Could not create the image.')).toBeInTheDocument();
  });

  it('names the button plainly without a card name', () => {
    render(
      <ShareCard filename="x.png">
        <p>Card</p>
      </ShareCard>,
    );
    expect(screen.getByRole('button', { name: 'Share image' })).toBeInTheDocument();
  });

  it('compact: shows a failure beside the icon button but keeps progress screen-reader only', async () => {
    let fail: (e: Error) => void = () => undefined;
    vi.mocked(shareElementAsImage).mockReturnValue(
      new Promise((_, reject) => {
        fail = reject;
      }),
    );
    render(
      <ShareCard compact filename="x.png" name="Trophy">
        <p>Card</p>
      </ShareCard>,
    );
    await userEvent.setup().click(screen.getByRole('button', { name: 'Share image: Trophy' }));
    expect(liveLine()).toHaveClass('sr-only');
    fail(new Error('boom'));
    expect(await screen.findByText('Could not create the image.')).not.toHaveClass('sr-only');
  });
});
