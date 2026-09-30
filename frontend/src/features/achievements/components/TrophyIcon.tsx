import type { CSSProperties } from 'react';
import type { Metal } from '../metals';
import { artManifestKey, LOCKED_STYLE, METAL_COLORS, ONE_OFF_COLOR } from '../metals';
import { trophyArt } from '../trophyArt.gen';

export interface TrophyIconProps {
  artKey: string;
  metal: Metal | null;
  locked: boolean;
  size: number;
}

/** Trophy art from the generated manifest; an inline SVG trophy tinted by metal when art is missing. */
export function TrophyIcon({ artKey, metal, locked, size }: TrophyIconProps) {
  const style: CSSProperties | undefined = locked ? LOCKED_STYLE : undefined;
  const art = trophyArt[artManifestKey(artKey, metal)];
  if (art) {
    return (
      <img
        src={size > 128 ? art.src : art.src128}
        srcSet={`${art.src128} 128w, ${art.src} 256w`}
        sizes={`${size}px`}
        width={size}
        height={size}
        alt=""
        style={style}
        className="shrink-0 rounded-full"
      />
    );
  }
  const color = metal === null ? ONE_OFF_COLOR : METAL_COLORS[metal];
  return (
    <svg
      viewBox="0 0 64 64"
      width={size}
      height={size}
      aria-hidden="true"
      focusable="false"
      style={style}
      className="shrink-0"
    >
      <circle cx="32" cy="32" r="30" fill="#2D5F3F" stroke={color} strokeWidth="3" />
      <path d="M22 16h20v9a10 10 0 0 1-20 0z" fill={color} />
      <path
        d="M22 19h-5a5 5 0 0 0 5 7M42 19h5a5 5 0 0 1-5 7"
        fill="none"
        stroke={color}
        strokeWidth="2.5"
      />
      <rect x="29" y="35" width="6" height="7" fill={color} />
      <rect x="23" y="42" width="18" height="5" rx="1.5" fill={color} />
    </svg>
  );
}
