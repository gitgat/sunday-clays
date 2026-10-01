import type { HomeWidget, HomeWidgetProps } from '../home/widgets';
import { SheetLead } from './components/SheetLead';

/**
 * The Sunday Sheet's lead (Plan 14): the issue's headline with its recap as the deck, then the
 * spotlight. Nothing outside an issue.
 */
function InsightsLead({ meId, issue }: HomeWidgetProps) {
  if (issue === undefined) return null;
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
