import { describe, expect, it } from 'vitest';
import {
  cardFilename,
  eventFilename,
  profileFilename,
  sheetPostFilename,
  slugify,
  trophyFilename,
} from './filenames';

describe('share filenames', () => {
  it('slugifies names, codes and titles', () => {
    expect(slugify('Hadley, Ike')).toBe('hadley-ike');
    expect(slugify('Ömer  Çelik!')).toBe('omer-celik');
    expect(slugify('!!!')).toBe('image');
  });

  it('names each kind of image', () => {
    expect(eventFilename('2026-09-13')).toBe('sunday-clays-2026-09-13.png');
    expect(profileFilename('Hadley, Ike')).toBe('sunday-clays-hadley-ike.png');
    expect(trophyFilename('clays_broken:3')).toBe('sunday-clays-trophy-clays-broken-3.png');
    expect(cardFilename('2025 at a glance')).toBe('sunday-clays-2025-at-a-glance.png');
    expect(sheetPostFilename('2026-09-27', 'New personal best for Ike Hadley: 46, and more.')).toBe(
      'sunday-sheet-2026-09-27-new-personal-best-for-ike-hadley.png',
    );
    expect(sheetPostFilename('2026-09-27', '!!!')).toBe('sunday-sheet-2026-09-27-image.png');
  });
});
