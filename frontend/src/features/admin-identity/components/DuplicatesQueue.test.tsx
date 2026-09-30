import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { doneJob } from '../../admin/mocks';
import type { DuplicatePair } from '../api';
import { duplicatePairs } from '../mocks';
import { DuplicatesQueue } from './DuplicatesQueue';

const merges: unknown[] = [];

function mergeReturns(sharedDates: number) {
  server.use(
    http.post('*/api/admin/shooters/merge', async ({ request }) => {
      const body = (await request.json()) as { dry_run: boolean };
      merges.push(body);
      return HttpResponse.json({ shared_dates: sharedDates, job_id: body.dry_run ? null : 71 });
    }),
  );
}

describe('DuplicatesQueue', () => {
  beforeEach(() => {
    merges.length = 0;
    server.use(
      http.get('*/api/admin/possible-duplicates', () => HttpResponse.json(duplicatePairs)),
      http.get('*/api/admin/jobs/:id', () => HttpResponse.json({ ...doneJob, id: 71 })),
    );
  });

  it('lists each pair with rounds and dates and offers a merge in either direction', async () => {
    // A side whose rounds are all hidden has no first/last event (DuplicateSideOut dates are nullable).
    const hiddenRounds: DuplicatePair = {
      a: {
        shooter_id: 160,
        name_key: 'beatrice@2025-02-23',
        display_name: 'Beatrice',
        n_rounds: 0,
        first_event: null,
        last_event: null,
      },
      b: {
        shooter_id: 161,
        name_key: 'mortlock beatrice',
        display_name: 'Mortlock, Beatrice',
        n_rounds: 3,
        first_event: '2026-02-01',
        last_event: '2026-09-06',
      },
    };
    server.use(
      http.get('*/api/admin/possible-duplicates', () =>
        HttpResponse.json([...duplicatePairs, hiddenRounds]),
      ),
    );
    renderWithProviders(<DuplicatesQueue />);
    const items = within(
      await screen.findByRole('list', { name: 'Possible duplicates' }),
    ).getAllByRole('listitem');
    expect(items).toHaveLength(3);
    expect(items[1]).toHaveTextContent(
      'Hammond, Bennett (1 rounds, Nov 3, 2024 – Nov 3, 2024) ↔ Hamond, Bennett (28 rounds, Nov 24, 2024 – Sep 27, 2026)',
    );
    const pair = within(items[1] as HTMLElement);
    expect(
      pair.getByRole('button', { name: 'Merge Hammond, Bennett into Hamond, Bennett' }),
    ).toBeInTheDocument();
    expect(
      pair.getByRole('button', { name: 'Merge Hamond, Bennett into Hammond, Bennett' }),
    ).toBeInTheDocument();
    expect(items[2]).toHaveTextContent(
      'Beatrice (0 rounds, no rounds) ↔ Mortlock, Beatrice (3 rounds, Feb 1, 2026 – Sep 6, 2026)',
    );
  });

  it('runs a dry run first and warns when the shooters share dates', async () => {
    mergeReturns(18);
    const user = userEvent.setup();
    renderWithProviders(<DuplicatesQueue />);
    await user.click(
      await screen.findByRole('button', { name: 'Merge Hamond, Bennett into Hammond, Bennett' }),
    );
    const confirm = await screen.findByRole('region', { name: 'Confirm merge' });
    expect(
      within(confirm).getByText(/both have rounds on 18 of the same dates/),
    ).toBeInTheDocument();
    expect(merges).toEqual([{ source_shooter_id: 140, target_shooter_id: 141, dry_run: true }]);
    await user.click(within(confirm).getByRole('button', { name: 'Merge anyway' }));
    expect(await screen.findByText('Merging #140 into #141: Done')).toBeInTheDocument();
    expect(merges.at(-1)).toEqual({
      source_shooter_id: 140,
      target_shooter_id: 141,
      dry_run: false,
    });
  });

  it('says there are no shared dates when the dry run finds none, and cancel sends nothing more', async () => {
    mergeReturns(0);
    const user = userEvent.setup();
    renderWithProviders(<DuplicatesQueue />);
    await user.click(
      await screen.findByRole('button', { name: 'Merge Pruett, Clay into Preutt, Clay' }),
    );
    const confirm = await screen.findByRole('region', { name: 'Confirm merge' });
    expect(within(confirm).getByText('No shared dates.')).toBeInTheDocument();
    await user.click(within(confirm).getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('region', { name: 'Confirm merge' })).not.toBeInTheDocument();
    expect(merges).toHaveLength(1);
  });

  it('previews a merge in the other direction too', async () => {
    mergeReturns(0);
    const user = userEvent.setup();
    renderWithProviders(<DuplicatesQueue />);
    await user.click(
      await screen.findByRole('button', { name: 'Merge Hammond, Bennett into Hamond, Bennett' }),
    );
    await screen.findByRole('region', { name: 'Confirm merge' });
    expect(merges).toEqual([{ source_shooter_id: 141, target_shooter_id: 140, dry_run: true }]);
  });

  it('shows a rejected merge next to the queue', async () => {
    server.use(
      http.post('*/api/admin/shooters/merge', () =>
        HttpResponse.json(
          { error: { code: 'merge_cycle', message: 'That merge would create a cycle' } },
          { status: 400 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<DuplicatesQueue />);
    await user.click(
      await screen.findByRole('button', { name: 'Merge Hamond, Bennett into Hammond, Bennett' }),
    );
    expect(await screen.findByRole('alert')).toHaveTextContent('That merge would create a cycle');
  });

  it('says when the queue is empty', async () => {
    server.use(http.get('*/api/admin/possible-duplicates', () => HttpResponse.json([])));
    renderWithProviders(<DuplicatesQueue />);
    expect(await screen.findByText('No possible duplicates.')).toBeInTheDocument();
  });

  it('shows the confirmation inside the pair that was clicked and moves focus to it', async () => {
    mergeReturns(2);
    const user = userEvent.setup();
    renderWithProviders(<DuplicatesQueue />);
    await user.click(
      await screen.findByRole('button', { name: 'Merge Pruett, Clay into Preutt, Clay' }),
    );
    const confirm = await screen.findByRole('region', { name: 'Confirm merge' });
    const items = within(screen.getByRole('list', { name: 'Possible duplicates' })).getAllByRole(
      'listitem',
    );
    const owners = items.filter((li) => li.contains(confirm));
    expect(owners).toHaveLength(1);
    expect(owners[0]).toHaveTextContent('Pruett, Clay');
    expect(within(confirm).getByRole('heading', { name: 'Confirm merge' })).toHaveFocus();
  });

  it('disables the merge buttons while a merge request is in flight', async () => {
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.post('*/api/admin/shooters/merge', async () => {
        await gate;
        return HttpResponse.json({ shared_dates: 0, job_id: null });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<DuplicatesQueue />);
    const first = await screen.findByRole('button', {
      name: 'Merge Hamond, Bennett into Hammond, Bennett',
    });
    await user.click(first);
    expect(first).toBeDisabled();
    expect(
      screen.getByRole('button', { name: 'Merge Pruett, Clay into Preutt, Clay' }),
    ).toBeDisabled();
    release();
    expect(await screen.findByRole('region', { name: 'Confirm merge' })).toBeInTheDocument();
    expect(first).toBeEnabled();
  });

  it('clears a failed merge when the admin cancels or starts another preview', async () => {
    server.use(
      http.post('*/api/admin/shooters/merge', async ({ request }) => {
        const body = (await request.json()) as { dry_run: boolean };
        if (body.dry_run) return HttpResponse.json({ shared_dates: 0, job_id: null });
        return HttpResponse.json(
          { error: { code: 'merge_cycle', message: 'That merge would create a cycle' } },
          { status: 400 },
        );
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<DuplicatesQueue />);
    await user.click(
      await screen.findByRole('button', { name: 'Merge Hamond, Bennett into Hammond, Bennett' }),
    );
    await user.click(
      within(await screen.findByRole('region', { name: 'Confirm merge' })).getByRole('button', {
        name: 'Merge',
      }),
    );
    expect(await screen.findByRole('alert')).toHaveTextContent('That merge would create a cycle');
    await user.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();

    await user.click(
      screen.getByRole('button', { name: 'Merge Hamond, Bennett into Hammond, Bennett' }),
    );
    await user.click(
      within(await screen.findByRole('region', { name: 'Confirm merge' })).getByRole('button', {
        name: 'Merge',
      }),
    );
    expect(await screen.findByRole('alert')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Merge Pruett, Clay into Preutt, Clay' }));
    await screen.findByText(/Merge Pruett, Clay/, { selector: 'p' });
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
