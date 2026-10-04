import { useState } from 'react';
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
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold">Club events</h1>
      <Tabs label="Club events" tabs={TABS} value={tab} onChange={setTab} />
      {tab === 'events' ? <EventsTab /> : <ContactsTab />}
    </div>
  );
}
