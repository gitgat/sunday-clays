import { expect, test } from './fixtures';
import { expectNoSideScroll, expectTapTargets, whenSettled } from './layout';

test('About opens from the nav and shows what, who, source and privacy', async ({
  page,
}, testInfo) => {
  await page.goto('/');
  if (testInfo.project.name === 'desktop') {
    await page
      .getByRole('navigation', { name: 'Main' })
      .getByRole('link', { name: 'About' })
      .click();
  } else {
    await page
      .getByRole('navigation', { name: 'Tabs' })
      .getByRole('button', { name: 'More' })
      .click();
    await page
      .getByRole('navigation', { name: 'More' })
      .getByRole('link', { name: 'About' })
      .click();
  }
  await expect(page).toHaveURL(/\/about/);
  await expect(page.getByRole('heading', { level: 1, name: 'About' })).toBeVisible();
  for (const name of [
    'What is Sunday Clays?',
    'Who built this?',
    'For the technically curious',
    'Your privacy',
  ]) {
    await expect(page.getByRole('heading', { level: 2, name })).toBeVisible();
  }
  await expect(
    page.getByRole('region', { name: 'Your privacy' }).getByRole('listitem'),
  ).toHaveCount(5);

  for (const [name, href] of [
    [/Read more on tcgc\.org/, 'https://tcgc.org/sunday-clays/'],
    [/gitgat\.com/, 'https://gitgat.com'],
    [/github\.com\/gitgat\/sunday-clays/, 'https://github.com/gitgat/sunday-clays'],
  ] as const) {
    const link = page.getByRole('main').getByRole('link', { name });
    await expect(link).toHaveAttribute('href', href);
    await expect(link).toHaveAttribute('target', '_blank');
    await expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  }

  await whenSettled(page);
  await expectTapTargets(page);
  await expectNoSideScroll(page);

  await page.getByRole('link', { name: 'See my scores' }).click();
  await expect(page).toHaveURL(/\/shooters\/187/);
});
