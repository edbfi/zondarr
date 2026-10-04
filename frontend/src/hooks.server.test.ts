import { afterEach, describe, expect, it, vi } from 'vitest';

const { privateEnv, publicEnv } = vi.hoisted(() => ({
	privateEnv: {
		INTERNAL_API_URL: 'http://localhost:8000',
		DEV_SKIP_AUTH: ''
	},
	publicEnv: {
		PUBLIC_API_URL: 'http://localhost:8000'
	}
}));

vi.mock('$app/env/private', () => privateEnv);

vi.mock('$app/env/public', () => publicEnv);

import { handle } from './hooks.server';

function makeEvent(pathname: string, accessToken: string | undefined = 'token') {
	return {
		cookies: {
			get: vi.fn((name: string) => (name === 'zondarr_access_token' ? accessToken : undefined))
		},
		locals: {},
		url: new URL(`http://frontend.local${pathname}`)
	};
}

describe('hooks onboarding guard', () => {
	afterEach(() => {
		vi.restoreAllMocks();
	});

	it('redirects authenticated users with onboarding in progress to /setup', async () => {
		vi.spyOn(globalThis, 'fetch').mockResolvedValue(
			new Response(
				JSON.stringify({
					id: '00000000-0000-0000-0000-000000000001',
					username: 'admin',
					email: null,
					auth_method: 'local',
					onboarding_required: true,
					onboarding_step: 'security'
				}),
				{ status: 200, headers: { 'content-type': 'application/json' } }
			)
		);
		const resolve = vi.fn();

		await expect(
			handle({ event: makeEvent('/dashboard'), resolve } as never)
		).rejects.toMatchObject({
			status: 302,
			location: '/setup'
		});
		expect(resolve).not.toHaveBeenCalled();
	});

	it('allows /setup while onboarding is in progress', async () => {
		vi.spyOn(globalThis, 'fetch').mockResolvedValue(
			new Response(
				JSON.stringify({
					id: '00000000-0000-0000-0000-000000000001',
					username: 'admin',
					email: null,
					auth_method: 'local',
					onboarding_required: true,
					onboarding_step: 'server'
				}),
				{ status: 200, headers: { 'content-type': 'application/json' } }
			)
		);
		const resolve = vi.fn(
			async () =>
				new Response('ok', {
					status: 200,
					headers: { 'content-type': 'text/plain', 'content-length': '2' }
				})
		);

		const response = await handle({ event: makeEvent('/setup'), resolve } as never);

		expect(response.status).toBe(200);
		expect(resolve).toHaveBeenCalledOnce();
	});

	it('redirects authenticated users away from /setup when onboarding is complete', async () => {
		vi.spyOn(globalThis, 'fetch').mockResolvedValue(
			new Response(
				JSON.stringify({
					id: '00000000-0000-0000-0000-000000000001',
					username: 'admin',
					email: null,
					auth_method: 'local',
					onboarding_required: false,
					onboarding_step: 'complete'
				}),
				{ status: 200, headers: { 'content-type': 'application/json' } }
			)
		);
		const resolve = vi.fn();

		await expect(handle({ event: makeEvent('/setup'), resolve } as never)).rejects.toMatchObject({
			status: 302,
			location: '/dashboard'
		});
		expect(resolve).not.toHaveBeenCalled();
	});
});
