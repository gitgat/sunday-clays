/** One labelled figure inside a Year in Review card. */
export function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex min-w-0 flex-col">
      <dt className="text-sm text-text-muted">{label}</dt>
      <dd className="break-words text-xl font-medium">{value}</dd>
    </div>
  );
}
