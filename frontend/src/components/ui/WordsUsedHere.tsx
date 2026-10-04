import { Fragment } from 'react';
import { Link } from 'react-router';
import { termById, type GlossaryTermId } from '../../features/glossary/terms';
import { useFeature } from '../../lib/features';

/** "Words used here:" links to the glossary (Plan 19 §3.2.2), while the glossary is visible. */
export function WordsUsedHere({ terms }: { terms: readonly GlossaryTermId[] }) {
  const { visible } = useFeature('tour_glossary');
  if (!visible) return null;
  return (
    <p className="flex flex-wrap items-center gap-x-1 text-sm text-text-muted">
      <span>Words used here:</span>
      {terms.map((id, index) => (
        <Fragment key={id}>
          {index > 0 && <span aria-hidden="true">·</span>}
          <Link to={`/glossary#${id}`} className="inline-flex min-h-11 items-center underline">
            {termById(id).term}
          </Link>
        </Fragment>
      ))}
    </p>
  );
}
