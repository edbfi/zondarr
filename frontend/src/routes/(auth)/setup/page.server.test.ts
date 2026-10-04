import { afterEach, describe, expect, it, vi } from 'vitest';

const { mockGetAuthMethods, mockReadFileSync } = vi.hoisted(() => ({
	mockGetAuthMethods: vi.fn(),
	mockReadFileSync: vi.fn()
}));

vi.mock('$app/env/private', () => ({
	BOOTSTRAP_TOKEN_FILE: '/run/secrets/bootstrap_token'
}));

vi.mock('node:fs', async (importOriginal) => {
	const actual = (await importOriginal()) as Record<string, unknown>;
	return {
		...actual,
		default: { ...actual, readFileSync: mockReadFileSync },
		readFileSync: mockReadFileSync
	};
});

vi.mock('$lib/api/auth', () => ({
	getAuthMethods: mockGetAuthMethods,
	getMe: vi.fn()
}));

vi.mock('$lib/server/setup-nonce', () => ({
	createValidatedNonce: () => 'validated-nonce'
}));

import { load } from './+page.server';

describe('setup page nonce cookie (M13)', () => {
	afterEach(() => {
		vi.clearAllMocks();
	});

	it.each([
		['https:', true],
		['http:', false]
	])('sets zondarr_setup_nonce over %s with secure: %s', async (protocol, secure) => {
		mockGetAuthMethods.mockResolvedValue({ setup_required: true });
		mockReadFileSync.mockReturnValue('setup-token-for-tests\n');
		const cookies = { get: vi.fn(), set: vi.fn() };

		await expect(
			load({
				fetch: vi.fn(),
				cookies,
				url: new URL(`${protocol}//frontend.local/setup?token=setup-token-for-tests`)
			} as never)
		).rejects.toMatchObject({ status: 302, location: '/setup' });

		expect(cookies.set).toHaveBeenCalledWith('zondarr_setup_nonce', 'validated-nonce', {
			httpOnly: true,
			secure,
			sameSite: 'strict',
			path: '/',
			maxAge: 600
		});
	});
});
