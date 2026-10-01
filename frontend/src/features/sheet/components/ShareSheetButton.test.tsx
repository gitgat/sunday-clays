import { act, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { shareLink } from '../../../lib/share';
import { renderWithProviders } from '../../../test/render';
import { sheetFixture } from '../mocks';
import { ShareSheetButton, sheetShareText } from './ShareSheetButton';

vi.mock('../../../lib/share', () => ({ shareLink: vi.fn() }));

afterEach(() => {
  vi.mocked(shareLink).mockReset();
});

describe('ShareSheetButton', () => {
  it('shares the issue link with the four numbers as text', async () => {
    vi.mocked(shareLink).mockResolvedValue('shared');
    const { user } = renderWithProviders(<ShareSheetButton issue={sheetFixture()} />);
    await user.click(screen.getByRole('button', { name: 'Share this Sheet' }));
    expect(shareLink).toHaveBeenCalledWith({
      title: 'The Sunday Sheet',
      text: 'The Sunday Sheet, Sep 27, 2026: 23 shooters, field median 39, top score 49, 13 trophies.',
      url: `${window.location.origin}/sheet/2026-09-27`,
    });
    expect(screen.queryByText('Link copied.')).toBeNull();
  });

  it('says when the link was copied instead, and when it failed', async () => {
    vi.mocked(shareLink).mockResolvedValueOnce('copied').mockRejectedValueOnce(new Error('no'));
    const { user } = renderWithProviders(<ShareSheetButton issue={sheetFixture()} />);
    await user.click(screen.getByRole('button', { name: 'Share this Sheet' }));
    expect(await screen.findByText('Link copied.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Share this Sheet' }));
    expect(await screen.findByText('Could not share the link.')).toBeInTheDocument();
  });

  it('clears "Link copied." on the next tap, so a second copy is announced again', async () => {
    let release: (v: 'copied') => void = () => undefined;
    vi.mocked(shareLink)
      .mockResolvedValueOnce('copied')
      .mockReturnValueOnce(
        new Promise((resolve) => {
          release = resolve;
        }),
      );
    const { user } = renderWithProviders(<ShareSheetButton issue={sheetFixture()} />);
    await user.click(screen.getByRole('button', { name: 'Share this Sheet' }));
    expect(await screen.findByText('Link copied.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Share this Sheet' }));
    expect(screen.queryByText('Link copied.')).toBeNull();
    release('copied');
    expect(await screen.findByText('Link copied.')).toBeInTheDocument();
  });

  it('clears "Link copied." after a few seconds', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      vi.mocked(shareLink).mockResolvedValue('copied');
      const { user } = renderWithProviders(<ShareSheetButton issue={sheetFixture()} />);
      await user.click(screen.getByRole('button', { name: 'Share this Sheet' }));
      expect(await screen.findByText('Link copied.')).toBeInTheDocument();
      await act(() => vi.advanceTimersByTimeAsync(5000));
      expect(screen.queryByText('Link copied.')).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it('says nothing when the share sheet is dismissed', async () => {
    vi.mocked(shareLink).mockResolvedValue('cancelled');
    const { user } = renderWithProviders(<ShareSheetButton issue={sheetFixture()} />);
    await user.click(screen.getByRole('button', { name: 'Share this Sheet' }));
    await waitFor(() => expect(shareLink).toHaveBeenCalledTimes(1));
    expect(screen.queryByText('Could not share the link.')).toBeNull();
    expect(screen.queryByText('Link copied.')).toBeNull();
    expect(screen.getByRole('button', { name: 'Share this Sheet' })).toBeEnabled();
  });

  it('is off while a share is in flight, so a double tap shares once', async () => {
    let release: (v: 'shared') => void = () => undefined;
    vi.mocked(shareLink).mockReturnValue(
      new Promise((resolve) => {
        release = resolve;
      }),
    );
    const { user } = renderWithProviders(<ShareSheetButton issue={sheetFixture()} />);
    const button = screen.getByRole('button', { name: 'Share this Sheet' });
    await user.click(button);
    expect(button).toBeDisabled();
    await user.click(button);
    expect(shareLink).toHaveBeenCalledTimes(1);
    release('shared');
    await waitFor(() => expect(button).toBeEnabled());
  });

  it('writes one shooter and one trophy in the singular', () => {
    const issue = sheetFixture({
      numbers: { shooters: 1, median: null, top_score: null, trophies: 1 },
    });
    expect(sheetShareText(issue)).toBe(
      'The Sunday Sheet, Sep 27, 2026: 1 shooter, field median —, top score —, 1 trophy.',
    );
  });
});
