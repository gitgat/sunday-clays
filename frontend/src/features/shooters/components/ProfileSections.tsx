import { Card } from '../../../components/ui/Card';
import type { ProfileSection } from '../sections';

export function ProfileSections({
  shooterId,
  sections,
}: {
  shooterId: number;
  sections: ProfileSection[];
}) {
  return (
    <>
      {sections.map(({ id, title, bare, Component }) =>
        bare === true ? (
          <Component key={id} shooterId={shooterId} />
        ) : (
          <Card key={id} title={title}>
            <Component shooterId={shooterId} />
          </Card>
        ),
      )}
    </>
  );
}
