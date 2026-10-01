import { describe, expect, it } from 'vitest';
import { feedKeys } from './feedKeys';
import { feedFixture, insightFixture, kudosFixture } from './mocks';

describe('feedKeys', () => {
  it('lists every insight a feed can show: lead cards, lists, kudos and More', () => {
    const feed = feedFixture({
      pinned: insightFixture({ key: 'pinned' }),
      hero: insightFixture({ key: 'hero' }),
      spotlight: insightFixture({ key: 'spot' }),
      conditions: insightFixture({ key: 'cond' }),
      top: [insightFixture({ key: 't1' })],
      kudos: kudosFixture(1),
      more: [insightFixture({ key: 'm1' })],
    });
    expect(feedKeys(feed)).toEqual(['pinned', 'hero', 'spot', 'cond', 't1', 'k-0', 'm1']);
  });

  it('is empty for an empty feed', () => {
    expect(feedKeys(feedFixture())).toEqual([]);
  });
});
