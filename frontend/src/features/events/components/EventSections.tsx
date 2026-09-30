import { Card } from '../../../components/ui/Card';
import type { EventSection } from '../sections';

export function EventSections({ date, sections }: { date: string; sections: EventSection[] }) {
  return (
    <>
      {sections.map(({ id, title, bare, Component }) =>
        bare === true ? (
          <Component key={id} date={date} />
        ) : (
          <Card key={id} title={title}>
            <Component date={date} />
          </Card>
        ),
      )}
    </>
  );
}
