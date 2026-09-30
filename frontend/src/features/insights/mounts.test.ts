import { describe, expect, it } from 'vitest';
import { pageTops } from '../../components/layout/pageTop';
import { eventSections } from '../events/sections';
import { homeWidgets } from '../home/widgets';
import { profileSections } from '../shooters/sections';

describe('insight mounts', () => {
  it('put insights at the top of the profile and the Sunday page, and in the home hero slot', () => {
    expect(profileSections.find((s) => s.id === 'insights')).toMatchObject({
      placement: 'top',
      bare: true,
    });
    expect(eventSections.find((s) => s.id === 'insights')).toMatchObject({
      placement: 'top',
      bare: true,
    });
    expect(homeWidgets.find((w) => w.id === 'insights')).toMatchObject({ slot: 'hero' });
  });

  it('put insights at the top of the club, leaderboards, records and stations pages', () => {
    expect(pageTops.find((p) => p.id === 'insights')?.pages).toEqual([
      'club',
      'leaderboards',
      'records',
      'stations',
    ]);
  });
});
