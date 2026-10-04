import type { ReactNode } from 'react';
import { Link } from 'react-router';

import { AdminPreviewBadge } from '../../../components/ui/AdminPreviewBadge';
import { Card } from '../../../components/ui/Card';
import { useFeature } from '../../../lib/features';
import { useRoundTypeLink } from '../../../lib/roundTypes';
import { LINK_PREVIEWS_LINE, privacyLines } from '../privacy';

/** The production shooter id of the site's builder; the profile link is only meaningful there. */
export const BUILDER_SHOOTER_ID = 187;

const LINK_CLASS = 'inline-flex min-h-11 items-center underline';

function ExternalLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className={LINK_CLASS}>
      {children}
      <span className="sr-only"> (opens in a new tab)</span>
    </a>
  );
}

export function AboutPage() {
  const previews = useFeature('link_previews');
  const clubEvents = useFeature('events');
  const privacy = privacyLines(clubEvents.visible);
  const profile = useRoundTypeLink(`/shooters/${BUILDER_SHOOTER_ID}`);
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold">About</h1>
      <Card title="What is Sunday Clays?" className="space-y-3">
        <p>
          Every Sunday from 10:00 to noon, Tri-County Gun Club members and their guests shoot a
          50-target sporting clays round in Sherwood. It runs under NSCA rules but isn’t sanctioned:
          a relaxed weekly shoot that welcomes new shooters and gives regulars structured practice.
        </p>
        <p>
          <ExternalLink href="https://tcgc.org/sunday-clays/">Read more on tcgc.org</ExternalLink>
        </p>
      </Card>
      <Card title="Who built this?" className="space-y-3">
        <p>
          Bryan Moran, one of the Sunday regulars. By day I’ve spent years building products people
          rely on; on the side I build things like ClaySmasher, a clay-shooting tracker. This site
          turns the club’s weekly score sheets into stats, trends, trophies and a bit of friendly
          fun.
        </p>
        <p className="flex flex-wrap gap-x-4">
          <Link to={profile} className={LINK_CLASS}>
            See my scores
          </Link>
          <ExternalLink href="https://gitgat.com">gitgat.com</ExternalLink>
        </p>
      </Card>
      <Card title="For the technically curious" className="space-y-3">
        <p>The whole site is open source: the code, the tests and how it was built.</p>
        <p>
          <ExternalLink href="https://github.com/gitgat/sunday-clays">
            github.com/gitgat/sunday-clays
          </ExternalLink>
        </p>
      </Card>
      <Card title="Your privacy" className="space-y-3">
        <ul className="list-disc space-y-2 pl-5">
          {privacy.map((line) => (
            <li key={line.text}>
              {line.text}
              {line.feature !== undefined && (
                <>
                  {' '}
                  <AdminPreviewBadge feature={line.feature} />
                </>
              )}
            </li>
          ))}
          {previews.visible && (
            <li>
              {LINK_PREVIEWS_LINE} <AdminPreviewBadge feature="link_previews" />
            </li>
          )}
        </ul>
      </Card>
    </div>
  );
}
