import { Card } from '../../../components/ui/Card';
import { Skeleton } from '../../../components/ui/Skeleton';

/**
 * Holds the masthead, the numbers, the lead and the first posts at about their final height while
 * the issue loads, so nothing jumps when it arrives. One status for the lot; the rest is hidden
 * from assistive tech.
 */
export function SheetSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      <Card className="min-h-36">
        <Skeleton label="Loading the Sunday Sheet" lines={4} />
      </Card>
      <div aria-hidden="true" className="flex flex-col gap-4">
        <Card className="min-h-36">
          <Skeleton lines={3} />
        </Card>
        <Card className="min-h-48">
          <Skeleton lines={5} />
        </Card>
        {[0, 1, 2, 3].map((i) => (
          <Card key={i} className="min-h-32">
            <Skeleton lines={3} />
          </Card>
        ))}
      </div>
    </div>
  );
}
