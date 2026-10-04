import { describe, expect, it } from 'vitest';
import { DIALOG_HEIGHT, DIALOG_WIDTH, placeDialog, type Box } from './placement';

const box = (left: number, top: number, width: number, height: number): Box => ({
  left,
  top,
  right: left + width,
  bottom: top + height,
});

function overlaps(a: Box, p: { left: number; top: number }): boolean {
  return (
    p.left < a.right &&
    p.left + DIALOG_WIDTH > a.left &&
    p.top < a.bottom &&
    p.top + DIALOG_HEIGHT > a.top
  );
}

describe('placeDialog', () => {
  it('goes to the right of the target when it fits', () => {
    expect(placeDialog(box(100, 200, 300, 100), 1440, 900)).toEqual({ left: 416, top: 200 });
  });

  it('flips to the left when the right side has no room (desktop Personal panel)', () => {
    const you = box(1048, 120, 368, 500);
    const spot = placeDialog(you, 1440, 900);
    expect(spot.left).toBe(1048 - 16 - DIALOG_WIDTH);
    expect(overlaps(you, spot)).toBe(false);
  });

  it('goes below a right-aligned control with no room on either side (tablet window picker)', () => {
    const window_ = box(300, 16, 440, 44);
    const spot = placeDialog(window_, 800, 900);
    expect(spot).toEqual({ left: 740 - DIALOG_WIDTH, top: 76 });
    expect(overlaps(window_, spot)).toBe(false);
  });

  it('goes above a target at the bottom when nothing else fits', () => {
    const wide = box(10, 700, 780, 150);
    const spot = placeDialog(wide, 800, 900);
    expect(spot.top).toBe(700 - 16 - DIALOG_HEIGHT);
    expect(overlaps(wide, spot)).toBe(false);
  });

  it('clamps inside the viewport as a last resort', () => {
    const huge = box(0, 0, 800, 900);
    const spot = placeDialog(huge, 800, 900);
    expect(spot.left).toBeGreaterThanOrEqual(16);
    expect(spot.top).toBeGreaterThanOrEqual(16);
  });

  it('never covers the target when any placement can avoid it', () => {
    for (const vw of [800, 1024, 1440]) {
      for (const left of [16, 200, 500, vw - 400]) {
        for (const top of [16, 300, 600]) {
          const target = box(left, top, 360, 60);
          expect(overlaps(target, placeDialog(target, vw, 900))).toBe(false);
        }
      }
    }
  });
});
