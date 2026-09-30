import { cx } from './cx';

export interface SkeletonProps {
  label?: string;
  lines?: number;
  className?: string;
}

export function Skeleton({ label = 'Loading', lines = 3, className }: SkeletonProps) {
  return (
    <div
      role="status"
      aria-busy="true"
      aria-label={label}
      className={cx('flex flex-col gap-2', className)}
    >
      <span className="sr-only">{label}</span>
      {Array.from({ length: lines }, (_, i) => (
        <div
          key={i}
          data-skeleton-line=""
          className="h-4 animate-pulse rounded bg-outline-variant/40"
        />
      ))}
    </div>
  );
}
