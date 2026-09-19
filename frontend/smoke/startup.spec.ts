import { expect, test } from '@playwright/test';

test('production setup hydrates and validates account input', async ({ page }) => {
	const url = new URL(process.env.SMOKE_URL ?? '');
	expect(url.protocol).toBe('http:');
	expect(url.hostname).toBe('127.0.0.1');
	const errors: string[] = [];
	page.on('pageerror', (error) => errors.push(error.message));
	await page.goto(`${url.origin}/setup?token=ci-ephemeral-setup-token`);
	await expect(page.getByText('Create Admin Account', { exact: true })).toBeVisible();
	await page.getByLabel('Username', { exact: true }).fill('smoke_admin');
	await page.getByLabel('Password', { exact: true }).fill('smoke-only-long-test-password');
	// This value is derived by hydrated Svelte state; server HTML cannot satisfy it.
	await expect(page.getByText('Strong', { exact: true })).toBeVisible();
	await page.getByLabel('Confirm password', { exact: true }).fill('different-smoke-password');
	await page.getByRole('button', { name: 'Create admin account', exact: true }).click();
	await expect(page.getByText('Passwords do not match', { exact: true })).toBeVisible();
	expect(errors).toEqual([]);
});
