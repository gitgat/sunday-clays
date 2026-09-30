import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { PLAY_INTERVAL_MS, usePlayer } from './usePlayer';

describe('usePlayer', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('starts paused on the latest frame', () => {
    const { result } = renderHook(() => usePlayer(4));
    expect(result.current.index).toBe(3);
    expect(result.current.playing).toBe(false);
  });

  it('plays from the first frame when started at the end and stops on the last frame', () => {
    const { result } = renderHook(() => usePlayer(3));
    act(() => {
      result.current.play();
    });
    expect(result.current.index).toBe(0);
    act(() => {
      vi.advanceTimersByTime(PLAY_INTERVAL_MS);
    });
    expect(result.current.index).toBe(1);
    act(() => {
      vi.advanceTimersByTime(PLAY_INTERVAL_MS);
    });
    expect(result.current.index).toBe(2);
    act(() => {
      vi.advanceTimersByTime(PLAY_INTERVAL_MS);
    });
    expect(result.current.index).toBe(2);
    expect(result.current.playing).toBe(false);
  });

  it('pause stops advancing and play resumes from the current frame', () => {
    const { result } = renderHook(() => usePlayer(5));
    act(() => {
      result.current.seek(1);
    });
    act(() => {
      result.current.play();
    });
    act(() => {
      vi.advanceTimersByTime(PLAY_INTERVAL_MS);
    });
    expect(result.current.index).toBe(2);
    act(() => {
      result.current.pause();
    });
    act(() => {
      vi.advanceTimersByTime(PLAY_INTERVAL_MS * 3);
    });
    expect(result.current.index).toBe(2);
  });

  it('seek clamps to the frame range and pauses', () => {
    const { result } = renderHook(() => usePlayer(3));
    act(() => {
      result.current.play();
    });
    act(() => {
      result.current.seek(9);
    });
    expect(result.current).toMatchObject({ index: 2, playing: false });
    act(() => {
      result.current.seek(-4);
    });
    expect(result.current.index).toBe(0);
  });

  it('handles an empty history', () => {
    const { result } = renderHook(() => usePlayer(0));
    expect(result.current.index).toBe(0);
  });
});

describe('usePlayer start', () => {
  it("starts on an insight's frame when given one", () => {
    const { result } = renderHook(() => usePlayer(5, PLAY_INTERVAL_MS, 2));
    expect(result.current.index).toBe(2);
  });
});
