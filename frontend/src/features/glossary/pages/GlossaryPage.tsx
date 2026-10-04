import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router';
import { AdminPreviewBadge } from '../../../components/ui/AdminPreviewBadge';
import { Button } from '../../../components/ui/Button';
import { cx } from '../../../components/ui/cx';
import { useMediaQuery } from '../../../lib/useMediaQuery';
import { REDUCED_MOTION_QUERY } from '../../tour/target';
import { GLOSSARY_TERMS } from '../terms';

const HIGHLIGHT_MS = 2000;

/** The term named by the URL hash, highlighted for 2 s after scrolling to it. */
function useHashHighlight(): string | null {
  const { hash } = useLocation();
  const reduced = useMediaQuery(REDUCED_MOTION_QUERY);
  const [highlighted, setHighlighted] = useState<string | null>(null);
  useEffect(() => {
    const id = decodeURIComponent(hash.slice(1));
    const el = id === '' ? null : document.getElementById(id);
    if (el === null) return undefined;
    el.scrollIntoView({ block: 'start', behavior: reduced ? 'auto' : 'smooth' });
    const show = requestAnimationFrame(() => setHighlighted(id));
    const hide = window.setTimeout(() => setHighlighted(null), HIGHLIGHT_MS);
    return () => {
      cancelAnimationFrame(show);
      window.clearTimeout(hide);
    };
  }, [hash, reduced]);
  return highlighted;
}

export function GlossaryPage() {
  const highlighted = useHashHighlight();
  const reduced = useMediaQuery(REDUCED_MOTION_QUERY);
  const navigate = useNavigate();
  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-medium">Glossary</h1>
          <AdminPreviewBadge feature="tour_glossary" />
        </div>
        <p className="text-text-muted">The words Sunday Clays uses, in plain English.</p>
      </header>
      <dl className="flex flex-col gap-1 rounded-card bg-surface">
        {GLOSSARY_TERMS.map(({ id, term, definition }) => (
          <div key={id} className="flex flex-col gap-1 p-3">
            <dt
              id={id}
              className={cx(
                'scroll-mt-28 rounded-button px-1 font-medium',
                highlighted === id && 'bg-elevated',
                !reduced && 'transition-colors duration-500',
              )}
            >
              {term}
            </dt>
            <dd className="px-1 text-sm text-text-muted">{definition}</dd>
          </div>
        ))}
      </dl>
      <Button variant="tonal" className="self-start" onClick={() => void navigate('/?tour=1')}>
        Take the tour again
      </Button>
    </div>
  );
}
