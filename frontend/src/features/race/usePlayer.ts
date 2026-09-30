import { useEffect, useState } from 'react';

export const PLAY_INTERVAL_MS = 1200;

export interface Player {
  index: number;
  playing: boolean;
  play: () => void;
  pause: () => void;
  seek: (index: number) => void;
}

/**
 * Frame cursor for the race: starts on `start` (an insight's Sunday) or the latest frame; Play
 * from the end restarts at 0.
 */
export function usePlayer(
  frameCount: number,
  intervalMs = PLAY_INTERVAL_MS,
  start: number | null = null,
): Player {
  const last = Math.max(0, frameCount - 1);
  const [picked, setPicked] = useState<number | null>(start);
  const [playing, setPlaying] = useState(false);
  const index = picked === null ? last : Math.min(picked, last);

  useEffect(() => {
    if (!playing) return undefined;
    const timer = window.setTimeout(() => {
      if (index >= last) setPlaying(false);
      else setPicked(index + 1);
    }, intervalMs);
    return () => {
      window.clearTimeout(timer);
    };
  }, [playing, index, last, intervalMs]);

  return {
    index,
    playing,
    play: () => {
      if (index >= last) setPicked(0);
      setPlaying(true);
    },
    pause: () => {
      setPlaying(false);
    },
    seek: (next) => {
      setPlaying(false);
      setPicked(Math.min(Math.max(next, 0), last));
    },
  };
}
