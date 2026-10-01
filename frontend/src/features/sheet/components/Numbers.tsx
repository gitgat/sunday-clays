import { Card } from '../../../components/ui/Card';
import { Stat } from '../../../components/ui/Stat';
import { formatScore } from '../../home/format';
import type { SheetIssue } from '../api';
import { sheetExplainers } from '../explainers';

/** The four numbers of the Sunday: shooters, field median, top score and trophies earned. */
export function Numbers({ issue }: { issue: SheetIssue }) {
  const n = issue.numbers;
  return (
    <Card title="This Sunday in numbers" subtitle="Not affected by the filters">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="Shooters" value={String(n.shooters)} explainer={sheetExplainers.shooters} />
        <Stat
          label="Field median"
          value={formatScore(n.median)}
          explainer={sheetExplainers.median}
        />
        <Stat label="Top score" value={formatScore(n.top_score)} explainer={sheetExplainers.top} />
        <Stat label="Trophies" value={String(n.trophies)} explainer={sheetExplainers.trophies} />
      </div>
    </Card>
  );
}
