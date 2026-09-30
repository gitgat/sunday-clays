export type Metal = 'bronze' | 'silver' | 'gold' | 'platinum' | 'diamond';

/** C12 metal colours, chosen for contrast on #1A4D2E / #2D5F3F. */
export const METAL_COLORS: Record<Metal, string> = {
  bronze: '#C98B5B',
  silver: '#C9D1D6',
  gold: '#E3B34A',
  platinum: '#E6EEF2',
  diamond: '#9FD8E6',
};

/** One-off trophies have no metal; they are tinted with the theme accent. */
export const ONE_OFF_COLOR = '#E8A77A';

/** C12: locked trophies render at 35% opacity in grayscale. */
export const LOCKED_STYLE = { opacity: 0.35, filter: 'grayscale(1)' } as const;

export function artManifestKey(artKey: string, metal: Metal | null): string {
  return metal === null ? artKey : `${artKey}-${metal}`;
}
