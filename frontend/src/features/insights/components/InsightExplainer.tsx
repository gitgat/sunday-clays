import { useContext } from 'react';
import { CardHeadingLevel } from '../../../components/ui/Card';
import type { Insight } from '../api';
import { Segments } from '../segments';

/** "How we worked it out": the insight's plain-language rules, one bullet each (spec §3.5). */
export function InsightExplainer({
  id,
  insight,
  you,
}: {
  id: string;
  insight: Insight;
  you: boolean;
}) {
  const level = useContext(CardHeadingLevel) + 1;
  const Heading = level === 3 ? 'h3' : 'h4';
  const bullets = you && insight.how_you !== null ? insight.how_you : insight.how;
  return (
    <div
      id={id}
      className="flex min-w-0 flex-col gap-2 rounded-card border border-outline-variant bg-surface p-3"
    >
      <Heading className="text-sm font-medium text-text">How we worked it out</Heading>
      <ul className="list-disc space-y-1 pl-5 text-sm text-text-muted">
        {bullets.map((bullet, i) => (
          <li key={String(i)}>
            <Segments segments={bullet} />
          </li>
        ))}
      </ul>
    </div>
  );
}
