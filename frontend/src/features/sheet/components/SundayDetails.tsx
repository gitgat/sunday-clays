import { Link } from 'react-router';
import { Card } from '../../../components/ui/Card';
import { useRoundTypeLink } from '../../../lib/roundTypes';
import { formatDay } from '../../home/format';

/** The rail's way to the full results of the issue's Sunday. */
export function SundayDetails({ date, latest }: { date: string; latest: boolean }) {
  const eventLink = useRoundTypeLink(`/events/${date}`);
  return (
    <Card title={latest ? 'Latest Sunday details' : 'Sunday details'}>
      <Link to={eventLink} className="inline-flex min-h-11 items-center underline">
        {`Full results, ${formatDay(date)}`}
      </Link>
    </Card>
  );
}
