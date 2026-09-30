/** The class every date input shares: 44 px tall, full width, the app's field look. */
export const DATE_INPUT_CLASS =
  'min-h-11 w-full rounded-button border border-outline-variant bg-surface px-3 text-sm text-text';

/** Shown in place of results when a custom range starts after it ends. */
export function RangeAlert() {
  return (
    <p role="alert" className="text-sm text-error">
      The start date must be on or before the end date.
    </p>
  );
}
