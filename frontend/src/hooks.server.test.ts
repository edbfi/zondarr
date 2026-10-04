import { parseSetCookie } from 'cookie';
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
	const url = new URL(`http://frontend.local${pathname}`);
	return {
		request: new Request(url),
		cookies: {
			get: vi.fn((name: string) => (name === 'zondarr_access_token' ? accessToken : undefined)),
			delete: vi.fn()
		},
		locals: {},
		url
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

const WRITE_METHODS = ['POST', 'PUT', 'PATCH', 'DELETE'] as const;
const APP_ORIGIN = 'http://frontend.local';

function makeWriteEvent(
	method: string,
	pathname: string,
	options: { origin?: string; json?: boolean; host?: string } = {}
) {
	const url = new URL(`${APP_ORIGIN}${pathname}`);
	const headers = new Headers();
	if (options.origin !== undefined) headers.set('origin', options.origin);
	if (options.host !== undefined) headers.set('host', options.host);
	if (options.json) headers.set('content-type', 'application/json');
	const hasBody = options.json && method !== 'GET' && method !== 'HEAD';
	return {
		request: new Request(url, {
			method,
			headers,
			body: hasBody
				? JSON.stringify({ username: 'admin', password: 'never-a-real-password' })
				: undefined
		}),
		cookies: { get: vi.fn(() => undefined), delete: vi.fn() },
		locals: {},
		url
	};
}

function okResolve() {
	return vi.fn(async () => new Response('ok', { status: 200 }));
}

describe('origin check for every write', () => {
	afterEach(() => {
		vi.restoreAllMocks();
	});

	describe.each(WRITE_METHODS)('%s', (method) => {
		it.each(['/api/auth/login', '/api/v1/wizards'])(
			'passes a same-origin JSON write to %s',
			async (path) => {
				const resolve = okResolve();
				const response = await handle({
					event: makeWriteEvent(method, path, { origin: APP_ORIGIN, json: true }),
					resolve
				} as never);
				expect(response.status).toBe(200);
				expect(resolve).toHaveBeenCalledOnce();
			}
		);

		it('passes a same-origin bodyless write', async () => {
			const resolve = okResolve();
			const response = await handle({
				event: makeWriteEvent(method, '/api/auth/logout', { origin: APP_ORIGIN }),
				resolve
			} as never);
			expect(response.status).toBe(200);
			expect(resolve).toHaveBeenCalledOnce();
		});

		const hostile: [string, string | undefined][] = [
			['a foreign Origin', 'http://evil.test'],
			['Origin: null', 'null'],
			['a missing Origin', undefined],
			['the https variant of the app origin', 'https://frontend.local'],
			['another port on the same host', 'http://frontend.local:8080']
		];
		describe.each(hostile)('rejects %s', (_label, origin) => {
			it.each([
				['a JSON write to /api/auth/login', '/api/auth/login', true],
				['a JSON write to /api/v1/wizards', '/api/v1/wizards', true],
				['a bodyless write to /api/auth/logout', '/api/auth/logout', false]
			])('for %s', async (_what, path, json) => {
				const fetchSpy = vi.spyOn(globalThis, 'fetch');
				const resolve = okResolve();
				const response = await handle({
					event: makeWriteEvent(method, path, { origin, json }),
					resolve
				} as never);
				expect(response.status).toBe(403);
				expect(await response.json()).toMatchObject({ error_code: 'FRONTEND_ORIGIN_MISMATCH' });
				expect(resolve).not.toHaveBeenCalled();
				expect(fetchSpy).not.toHaveBeenCalled();
			});
		});

		it('ignores a Host header naming another host', async () => {
			const rebound = await handle({
				event: makeWriteEvent(method, '/api/auth/login', {
					origin: 'http://attacker.test',
					host: 'attacker.test',
					json: true
				}),
				resolve: okResolve()
			} as never);
			expect(rebound.status).toBe(403);

			const resolve = okResolve();
			const sameOrigin = await handle({
				event: makeWriteEvent(method, '/api/auth/login', {
					origin: APP_ORIGIN,
					host: 'attacker.test',
					json: true
				}),
				resolve
			} as never);
			expect(sameOrigin.status).toBe(200);
			expect(resolve).toHaveBeenCalledOnce();
		});
	});

	it.each(['GET', 'HEAD', 'OPTIONS'])(
		'leaves %s untouched, whatever its Origin',
		async (method) => {
			const resolve = okResolve();
			const response = await handle({
				event: makeWriteEvent(method, '/api/v1/wizards', { origin: 'http://evil.test' }),
				resolve
			} as never);
			expect(response.status).toBe(200);
			expect(resolve).toHaveBeenCalledOnce();
		}
	);
});

describe('cookie Secure flag follows the request origin (M13)', () => {
	afterEach(() => {
		vi.restoreAllMocks();
	});

	it.each([
		['https:', true],
		['http:', false]
	])('deletes stale token cookies over %s with secure: %s', async (protocol, secure) => {
		vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 401 }));
		const event = makeEvent('/dashboard', 'expired-token');
		Object.assign(event, { url: new URL(`${protocol}//frontend.local/dashboard`) });

		await expect(handle({ event, resolve: vi.fn() } as never)).rejects.toMatchObject({
			status: 302,
			location: '/login'
		});
		expect(event.cookies.delete).toHaveBeenCalledWith('zondarr_access_token', {
			path: '/',
			secure
		});
		expect(event.cookies.delete).toHaveBeenCalledWith('zondarr_refresh_token', {
			path: '/',
			secure
		});
	});
});

describe('session refresh relays backend cookies with Secure from the request origin (M16)', () => {
	afterEach(() => {
		vi.restoreAllMocks();
	});

	const user = {
		id: '00000000-0000-0000-0000-000000000001',
		username: 'admin',
		email: null,
		auth_method: 'local',
		onboarding_required: false,
		onboarding_step: 'complete'
	};

	/** /api/auth/me answers 401, the refresh answers with `setCookies`, the retried /me 200. */
	function backendRefreshing(setCookies: string[]) {
		const refreshed = new Headers({ 'content-type': 'application/json' });
		for (const cookie of setCookies) refreshed.append('set-cookie', cookie);
		return vi
			.spyOn(globalThis, 'fetch')
			.mockResolvedValueOnce(new Response('{}', { status: 401 }))
			.mockResolvedValueOnce(new Response('{}', { status: 200, headers: refreshed }))
			.mockResolvedValueOnce(Response.json(user));
	}

	function refreshEvent(protocol: string) {
		const url = new URL(`${protocol}//frontend.local/dashboard`);
		return {
			request: new Request(url),
			cookies: {
				get: vi.fn((name: string) =>
					name === 'zondarr_access_token' ? 'expired-access' : 'refresh-token'
				),
				set: vi.fn(),
				delete: vi.fn(),
				parse: parseSetCookie
			},
			locals: {} as { user?: unknown },
			url
		};
	}

	async function refresh(protocol: string, setCookies: string[]) {
		backendRefreshing(setCookies);
		const event = refreshEvent(protocol);
		const resolve = okResolve();
		const response = await handle({ event, resolve } as never);
		expect(response.status).toBe(200);
		expect(event.locals.user).toEqual(user);
		return event.cookies.set;
	}

	it('drops the backend Secure over http and keeps every other attribute', async () => {
		const set = await refresh('http:', [
			'zondarr_access_token=new-access; HttpOnly; Max-Age=900; Path=/; SameSite=lax; Secure',
			'zondarr_refresh_token=new-refresh; HttpOnly; Max-Age=604800; Path=/; SameSite=lax; Secure'
		]);
		expect(set).toHaveBeenCalledTimes(2);
		expect(set).toHaveBeenCalledWith('zondarr_access_token', 'new-access', {
			httpOnly: true,
			maxAge: 900,
			path: '/',
			sameSite: 'lax',
			secure: false
		});
		expect(set).toHaveBeenCalledWith('zondarr_refresh_token', 'new-refresh', {
			httpOnly: true,
			maxAge: 604800,
			path: '/',
			sameSite: 'lax',
			secure: false
		});
	});

	it('adds Secure over https when the backend did not set it', async () => {
		const set = await refresh('https:', [
			'zondarr_access_token=new-access; HttpOnly; Max-Age=900; Path=/; SameSite=lax',
			'zondarr_refresh_token=new-refresh; HttpOnly; Max-Age=604800; Path=/; SameSite=lax'
		]);
		expect(set).toHaveBeenCalledWith(
			'zondarr_access_token',
			'new-access',
			expect.objectContaining({ secure: true, maxAge: 900 })
		);
		expect(set).toHaveBeenCalledWith(
			'zondarr_refresh_token',
			'new-refresh',
			expect.objectContaining({ secure: true, maxAge: 604800 })
		);
	});

	it.each([
		['http:', false],
		['https:', true]
	])(
		'over %s keeps the backend Path, Expires and SameSite and its missing HttpOnly',
		async (protocol, secure) => {
			const set = await refresh(protocol, [
				'zondarr_access_token=new-access; Path=/app; Expires=Wed, 21 Oct 2026 07:28:00 GMT; SameSite=Strict',
				'unrelated=ignored; Path=/'
			]);
			expect(set).toHaveBeenCalledOnce();
			expect(set).toHaveBeenCalledWith('zondarr_access_token', 'new-access', {
				httpOnly: false,
				expires: new Date('2026-10-21T07:28:00Z'),
				path: '/app',
				sameSite: 'strict',
				secure
			});
		}
	);
});
