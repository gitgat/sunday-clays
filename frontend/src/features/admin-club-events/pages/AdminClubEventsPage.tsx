import { useState } from 'react';
import { Link } from 'react-router';
import { useFeature } from '../../../lib/features';
import { Tabs } from '../../../components/ui/Tabs';
import { ContactsTab } from '../components/ContactsTab';
import { EventsTab } from '../components/EventsTab';

type Tab = 'events' | 'contacts';
const TABS = [
  { value: 'events', label: 'Events' },
  { value: 'contacts', label: 'Contacts' },
] as const;

/** /admin/club-events (§5.7.5): served whether the events switch is on or off (D1). */
export function AdminClubEventsPage() {
  const [tab, setTab] = useState<Tab>('events');
  const { preview } = useFeature('events');
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold">Club events</h1>
      {preview && (
        <p className="text-sm text-text-muted">
          {"Members can't see club events until Club events is turned on in "}
          <Link to="/admin/features" className="text-accent underline">
            Features
          </Link>
          .
        </p>
      )}
      <Tabs label="Club events" tabs={TABS} value={tab} onChange={setTab} />
      {tab === 'events' ? <EventsTab /> : <ContactsTab />}
    </div>
  );
}
