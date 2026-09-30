import { describe, expect, it } from 'vitest';
import { eventSection } from './eventSection';
import { homeWidget } from './homeWidget';
import { NextTrophy } from './NextTrophy';
import { profileSection } from './profileSection';
import { TrophiesToday } from './TrophiesToday';
import { TrophyCase } from './TrophyCase';

describe('glob exports (C10)', () => {
  it('registers the Trophy Case as a profile section', () => {
    expect(profileSection).toEqual({
      id: 'trophy-case',
      title: 'Trophy Case',
      order: 60,
      Component: TrophyCase,
    });
  });

  it('registers Trophies earned today as an event section', () => {
    expect(eventSection).toEqual({
      id: 'trophies-today',
      title: 'Trophies earned today',
      order: 60,
      Component: TrophiesToday,
    });
  });

  it('registers Your next trophy in the home me slot', () => {
    expect(homeWidget).toEqual({ id: 'next-trophy', order: 30, slot: 'me', Component: NextTrophy });
  });
});
