import { useState } from 'react';
import { Button } from '../../../components/ui/Button';
import { clearMe, getMe, setMe } from '../../../lib/me';

/** "That's me" personalization (spec §4): stored in localStorage via lib/me. */
export function MeButton({ shooterId }: { shooterId: number }) {
  const [me, setMeState] = useState<number | null>(() => getMe());
  const isMe = me === shooterId;
  function toggle() {
    if (isMe) {
      clearMe();
      setMeState(null);
    } else {
      setMe(shooterId);
      setMeState(shooterId);
    }
  }
  return (
    <Button variant={isMe ? 'primary' : 'tonal'} aria-pressed={isMe} onClick={toggle}>
      {isMe ? 'This is you' : "That's me"}
    </Button>
  );
}
