import { describe, expect, it } from 'vitest';
import { shooterList } from '../shooters/mocks';
import { matchesName, searchShooters } from './picker';

describe('the "Who are you?" picker', () => {
  it('ignores case, commas and word order', () => {
    expect(matchesName('ike had', 'Hadley, Ike')).toBe(true);
    expect(matchesName('HADLEY,', 'Hadley, Ike')).toBe(true);
    expect(matchesName('ike x', 'Hadley, Ike')).toBe(false);
    expect(matchesName('   ', 'Hadley, Ike')).toBe(false);
  });

  it('hides deceased shooters and stops at eight', () => {
    expect(searchShooters(shooterList, 'gilchrist')).toEqual([]);
    expect(searchShooters(shooterList, 'ike').map((s) => s.display_name)).toEqual(['Hadley, Ike']);
    const many = Array.from({ length: 12 }, (_, n) => ({
      ...(shooterList[1] as (typeof shooterList)[number]),
      shooter_id: 100 + n,
      display_name: `Quill, Dana ${n}`,
    }));
    expect(searchShooters(many, 'dana')).toHaveLength(8);
  });
});
