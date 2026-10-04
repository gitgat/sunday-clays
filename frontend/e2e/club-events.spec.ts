import { expect, test } from './fixtures';
import { expectNoSideScroll, whenSettled } from './layout';

// Read-only projects (desktop 1440 × 900, mobile 390 × 844): the `events` switch is off on the e2e
// stack (compose.test.yaml FEATURES_DEFAULT_ON does not list it), which is the production default.
test('club events stay invisible to members while the switch is off', async ({
  page,
}, testInfo) => {
  await page.goto('/');
  await whenSettled(page);
  // Positive controls first: the Glossary entry and the milestone card are switched on in the e2e
  // stack, so they only appear once /api/features has answered. Until then every launch-switched
  // piece renders nothing and the absence checks below would pass whether or not the gate works.
  await expect(page.getByRole('region', { name: /^Club milestone/ })).toBeVisible();
  if (testInfo.project.name === 'desktop') {
    await expect(
      page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Glossary' }),
    ).toBeVisible();
    await expect(
      page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Club events' }),
    ).toHaveCount(0);
  } else {
    await page
      .getByRole('navigation', { name: 'Tabs' })
      .getByRole('button', { name: 'More' })
      .click();
    await expect(
      page.getByRole('navigation', { name: 'More' }).getByRole('link', { name: 'About' }),
    ).toBeVisible();
    await expect(
      page.getByRole('navigation', { name: 'More' }).getByRole('link', { name: 'Glossary' }),
    ).toBeVisible();
    await expect(
      page.getByRole('navigation', { name: 'More' }).getByRole('link', { name: 'Club events' }),
    ).toHaveCount(0);
    await page.keyboard.press('Escape');
  }
  await expect(page.getByRole('region', { name: 'Coming up' })).toHaveCount(0);

  const api = await page.request.get('/api/club-events');
  expect(api.status()).toBe(404);
  expect(await api.json()).toEqual({ detail: 'Not Found' });

  await page.goto('/club-events');
  await expect(page.getByText('Page not found')).toBeVisible();
  await expectNoSideScroll(page);

  await page.goto('/about');
  const privacy = page.getByRole('region', { name: 'Your privacy' });
  await expect(privacy).toBeVisible();
  // Positive control: the link-preview line is switched on and shows only once the switches load.
  await expect(privacy.getByText(/Links shared in chat apps/)).toBeVisible();
  await expect(privacy.getByText(/If you sign up for a club event/)).toHaveCount(0);
  await expect(privacy.getByText(/Only organizers see emails/)).toHaveCount(0);
  await expectNoSideScroll(page);
});
