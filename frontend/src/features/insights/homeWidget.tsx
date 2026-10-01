import type { HomeWidget, HomeWidgetProps } from '../home/widgets';
import { HomeInsights } from './components/FeedSections';
import { SheetLead } from './components/SheetLead';

/**
 * The Sunday Sheet's lead (Plan 14): the issue's headline with its recap as the deck, then the
 * spotlight. Without an issue (the Home page, until Task 9 retires it) it is the home feed.
 */
function InsightsLead({ meId, issue }: HomeWidgetProps) {
  if (issue === undefined) return <HomeInsights meId={meId} />;
  return (
    <SheetLead
      headline={issue.headline}
      recap={issue.recap}
      spotlight={issue.spotlight}
      meId={meId}
      date={issue.masthead.date}
    />
  );
}

export const homeWidget: HomeWidget = {
  id: 'insights',
  order: 0,
  slot: 'hero',
  Component: InsightsLead,
};
