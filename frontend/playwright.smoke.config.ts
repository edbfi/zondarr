import { defineConfig } from '@playwright/test';

export default defineConfig({
	testDir: './smoke',
	outputDir: './test-results',
	workers: 1,
	retries: 0,
	timeout: 30_000,
	forbidOnly: true,
	use: {
		browserName: 'chromium',
		trace: 'retain-on-failure',
		screenshot: 'only-on-failure'
	}
});
