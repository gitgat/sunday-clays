import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import { onThisDayPost, postFixture, trophyPost } from '../mocks';
import { PostCard } from './PostCard';

describe('PostCard sharing', () => {
  it.each([
    ['an insight', postFixture()],
    ['a trophy', trophyPost],
    ['an "On this day" look-back', onThisDayPost],
  ])('%s post links "See why" and shares as an image', (_name, post) => {
    renderWithProviders(
      <ul>
        <PostCard
          post={post}
          date="2026-09-27"
          deviceId={null}
          bumps={undefined}
          meId={null}
          noteId="n"
        />
      </ul>,
    );
    const card = screen.getByRole('listitem');
    expect(within(card).getByRole('link', { name: /^See why: / })).toBeInTheDocument();
    expect(
      within(card).getByRole('button', { name: 'Share image', description: /\S/ }),
    ).toBeInTheDocument();
  });

  it('reads the see-why link in the second person on the viewer’s own post', () => {
    renderWithProviders(
      <ul>
        <PostCard
          post={postFixture()}
          date="2026-09-27"
          deviceId={null}
          bumps={undefined}
          meId={3}
          noteId="n"
        />
      </ul>,
    );
    expect(
      screen.getByRole('link', { name: 'See why: Your scores, with the personal-best line' }),
    ).toBeInTheDocument();
  });
});
