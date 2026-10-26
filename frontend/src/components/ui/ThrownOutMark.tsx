/** A plain muted asterisk beside a number that comes from a Sunday with a station thrown out. */
export function ThrownOutMark({ phrase }: { phrase: string }) {
  return (
    <span className="ml-0.5 text-text-muted" title={phrase}>
      <span aria-hidden="true">*</span>
      <span className="sr-only"> {phrase}</span>
    </span>
  );
}
