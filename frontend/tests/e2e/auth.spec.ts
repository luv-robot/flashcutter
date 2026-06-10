import { expect, test } from '@playwright/test';

test('shows the trial login gate', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Flashcutter' })).toBeVisible();
  await expect(page.getByLabel('手机号')).toBeVisible();
  await expect(page.getByLabel('密码')).toBeVisible();
  await expect(page.getByRole('button', { name: '登录' })).toBeVisible();
  await expect(page.getByText('当前试用环境暂不开放自助注册')).toBeVisible();
});
