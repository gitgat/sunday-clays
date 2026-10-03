export interface Box {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

export const DIALOG_WIDTH = 360;
/** A generous height for the dialog's content, used to decide whether it fits above or below. */
export const DIALOG_HEIGHT = 280;
const GAP = 16;
const EDGE = 16;

const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(value, max));

/**
 * Where the tour dialog sits so it never covers the target it points at: to the right if there
 * is room, else to the left, else below, else above. Only when none fit (a target as big as the
 * screen) does it clamp inside the viewport and overlap.
 */
export function placeDialog(box: Box, vw: number, vh: number): { left: number; top: number } {
  const sideTop = clamp(box.top, EDGE, vh - DIALOG_HEIGHT);
  const rowLeft = clamp(box.right - DIALOG_WIDTH, EDGE, vw - DIALOG_WIDTH - EDGE);
  if (box.right + GAP + DIALOG_WIDTH <= vw - EDGE) return { left: box.right + GAP, top: sideTop };
  if (box.left - GAP - DIALOG_WIDTH >= EDGE) {
    return { left: box.left - GAP - DIALOG_WIDTH, top: sideTop };
  }
  if (box.bottom + GAP + DIALOG_HEIGHT <= vh - EDGE) {
    return { left: rowLeft, top: box.bottom + GAP };
  }
  if (box.top - GAP - DIALOG_HEIGHT >= EDGE) {
    return { left: rowLeft, top: box.top - GAP - DIALOG_HEIGHT };
  }
  return { left: rowLeft, top: sideTop };
}
