import type { Recap } from '../api';
import { formatRecap } from '../format';

/** The recap in the app's card style (600 px), rendered on screen as the image preview. */
export function RecapImageCard({ recap }: { recap: Recap }) {
  const [title, ...rest] = formatRecap(recap).text.split('\n\n');
  return (
    <article className="flex w-[600px] max-w-full flex-col gap-3 rounded-card bg-surface p-5 text-text">
      <h2 className="text-lg font-bold whitespace-pre-line">{title}</h2>
      {rest.map((block) => (
        <p key={block} className="text-sm whitespace-pre-line">
          {block}
        </p>
      ))}
    </article>
  );
}
