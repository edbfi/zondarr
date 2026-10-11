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

import { BACKEND_DEADLINE_MS } from '$lib/server/backend-relay';
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

	/**
	 * What event.cookies.parse (cookie's parseSetCookie) returns for each header below, written out
	 * by hand so the test does not import a package this app does not declare.
	 */
	const PARSED: Record<string, Record<string, unknown>> = {
		'zondarr_access_token=new-access; HttpOnly; Max-Age=900; Path=/; SameSite=lax; Secure': {
			name: 'zondarr_access_token',
			value: 'new-access',
			httpOnly: true,
			maxAge: 900,
			path: '/',
			sameSite: 'lax',
			secure: true
		},
		'zondarr_refresh_token=new-refresh; HttpOnly; Max-Age=604800; Path=/; SameSite=lax; Secure': {
			name: 'zondarr_refresh_token',
			value: 'new-refresh',
			httpOnly: true,
			maxAge: 604800,
			path: '/',
			sameSite: 'lax',
			secure: true
		},
		'zondarr_access_token=new-access; HttpOnly; Max-Age=900; Path=/; SameSite=lax': {
			name: 'zondarr_access_token',
			value: 'new-access',
			httpOnly: true,
			maxAge: 900,
			path: '/',
			sameSite: 'lax'
		},
		'zondarr_refresh_token=new-refresh; HttpOnly; Max-Age=604800; Path=/; SameSite=lax': {
			name: 'zondarr_refresh_token',
			value: 'new-refresh',
			httpOnly: true,
			maxAge: 604800,
			path: '/',
			sameSite: 'lax'
		},
		'zondarr_access_token=new-access; Path=/app; Expires=Wed, 21 Oct 2026 07:28:00 GMT; SameSite=Strict':
			{
				name: 'zondarr_access_token',
				value: 'new-access',
				path: '/app',
				expires: new Date('2026-10-21T07:28:00Z'),
				sameSite: 'strict'
			},
		'unrelated=ignored; Path=/': { name: 'unrelated', value: 'ignored', path: '/' }
	};
	const parse = (header: string) => {
		const parsed = PARSED[header];
		if (!parsed) throw new Error(`no parsed fixture for ${header}`);
		return parsed;
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
				parse
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

describe('session check: budget, cancellation and transient failures', () => {
	afterEach(() => {
		vi.useRealTimers();
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

	/** An event with a cookie jar that `set` updates, so the retried /me sees a rotated token. */
	function sessionEvent(
		pathname = '/dashboard',
		{ refreshToken }: { refreshToken?: string } = { refreshToken: 'refresh-token' }
	) {
		const client = new AbortController();
		const url = new URL(`http://frontend.local${pathname}`);
		const jar = new Map([['zondarr_access_token', 'expired-access']]);
		if (refreshToken) jar.set('zondarr_refresh_token', refreshToken);
		const event = {
			request: new Request(url, { signal: client.signal }),
			cookies: {
				get: vi.fn((name: string) => jar.get(name)),
				set: vi.fn((name: string, value: string) => {
					jar.set(name, value);
				}),
				delete: vi.fn(),
				parse: (header: string) => {
					const [name, value] = (header.split(';')[0] ?? '').split('=');
					return { name, value, path: '/' };
				}
			},
			locals: {} as { user?: unknown },
			url
		};
		return { client, event };
	}

	/** A backend call that settles only when its signal aborts. */
	const stalled = (init?: RequestInit) =>
		new Promise<Response>((_resolve, reject) => {
			init?.signal?.addEventListener('abort', () =>
				reject(new DOMException('aborted', 'AbortError'))
			);
		});
	const rotated = () =>
		new Response('{}', {
			status: 200,
			headers: [
				['set-cookie', 'zondarr_access_token=new-access; Path=/'],
				['set-cookie', 'zondarr_refresh_token=new-refresh; Path=/']
			]
		});

	async function expectUnavailable(response: Response) {
		expect(response.status).toBe(503);
		expect(await response.json()).toEqual({ detail: 'Authentication temporarily unavailable' });
	}

	it('answers 503 on a protected page and keeps the cookies when /me passes its budget', async () => {
		vi.useFakeTimers();
		vi.spyOn(globalThis, 'fetch').mockImplementation((_input, init) => stalled(init));
		const { event } = sessionEvent();
		const pending = handle({ event, resolve: okResolve() } as never);
		await vi.advanceTimersByTimeAsync(5000);
		await expectUnavailable(await pending);
		expect(event.cookies.delete).not.toHaveBeenCalled();
		expect(event.locals.user).toBeNull();
	});

	it.each([500, 503])('treats a %i from /me as transient', async (status) => {
		vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status }));
		const { event } = sessionEvent();
		await expectUnavailable(await handle({ event, resolve: okResolve() } as never));
		expect(event.cookies.delete).not.toHaveBeenCalled();
	});

	it('lets a public page through while the backend is unavailable', async () => {
		vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 503 }));
		const { event } = sessionEvent('/login');
		const resolve = okResolve();
		expect((await handle({ event, resolve } as never)).status).toBe(200);
		expect(resolve).toHaveBeenCalledOnce();
	});

	it('keeps the cookies when the refresh fails with a 503', async () => {
		vi.spyOn(globalThis, 'fetch')
			.mockResolvedValueOnce(new Response('{}', { status: 401 }))
			.mockResolvedValueOnce(new Response('{}', { status: 503 }));
		const { event } = sessionEvent();
		await expectUnavailable(await handle({ event, resolve: okResolve() } as never));
		expect(event.cookies.delete).not.toHaveBeenCalled();
	});

	it.each([
		['the backend rejects the refresh', { refreshToken: 'refresh-token' }, 2],
		['there is no refresh token', {}, 1]
	])('logs out when %s', async (_label, options, calls) => {
		const spy = vi
			.spyOn(globalThis, 'fetch')
			.mockResolvedValueOnce(new Response('{}', { status: 401 }))
			.mockResolvedValueOnce(new Response('{}', { status: 401 }));
		const { event } = sessionEvent('/dashboard', options);
		await expect(handle({ event, resolve: okResolve() } as never)).rejects.toMatchObject({
			status: 302,
			location: '/login'
		});
		expect(spy).toHaveBeenCalledTimes(calls);
		expect(event.cookies.delete).toHaveBeenCalledTimes(2);
	});

	it('gives the refresh the relay deadline and keeps the cookies when it passes', async () => {
		vi.useFakeTimers();
		const spy = vi
			.spyOn(globalThis, 'fetch')
			.mockResolvedValueOnce(new Response('{}', { status: 401 }))
			.mockImplementationOnce((_input, init) => stalled(init));
		const { event } = sessionEvent();
		const pending = handle({ event, resolve: okResolve() } as never);
		await vi.advanceTimersByTimeAsync(BACKEND_DEADLINE_MS - 1);
		const refreshSignal = spy.mock.calls[1]?.[1]?.signal;
		expect(refreshSignal?.aborted).toBe(false);
		await vi.advanceTimersByTimeAsync(1);
		expect(refreshSignal?.aborted).toBe(true);
		await expectUnavailable(await pending);
		expect(event.cookies.delete).not.toHaveBeenCalled();
	});

	it('cancels the refresh with the request', async () => {
		const spy = vi
			.spyOn(globalThis, 'fetch')
			.mockResolvedValueOnce(new Response('{}', { status: 401 }))
			.mockImplementationOnce((_input, init) => stalled(init));
		const { client, event } = sessionEvent();
		const pending = handle({ event, resolve: okResolve() } as never);
		await vi.waitFor(() => expect(spy).toHaveBeenCalledTimes(2));
		client.abort();
		await expectUnavailable(await pending);
		expect(event.cookies.delete).not.toHaveBeenCalled();
	});

	it('shares the budget between both /me calls and keeps rotated cookies when it runs out', async () => {
		vi.useFakeTimers();
		const spy = vi
			.spyOn(globalThis, 'fetch')
			.mockImplementationOnce(
				() =>
					new Promise<Response>((done) =>
						setTimeout(() => done(new Response('{}', { status: 401 })), 4000)
					)
			)
			.mockResolvedValueOnce(rotated())
			.mockImplementationOnce((_input, init) => stalled(init));
		const { event } = sessionEvent();
		const pending = handle({ event, resolve: okResolve() } as never);
		await vi.advanceTimersByTimeAsync(4000);
		const retrySignal = () => spy.mock.calls[2]?.[1]?.signal;
		expect(retrySignal()?.aborted).toBe(false);
		await vi.advanceTimersByTimeAsync(999);
		expect(retrySignal()?.aborted).toBe(false);
		await vi.advanceTimersByTimeAsync(1);
		expect(retrySignal()?.aborted).toBe(true);
		await expectUnavailable(await pending);
		expect(spy.mock.calls[2]?.[1]?.headers).toEqual({ Cookie: 'zondarr_access_token=new-access' });
		expect(event.cookies.set).toHaveBeenCalledWith(
			'zondarr_access_token',
			'new-access',
			expect.anything()
		);
		expect(event.cookies.delete).not.toHaveBeenCalled();
	});

	// The refresh takes longer than the whole budget; the retried /me still gets what the first
	// one left (1 s), and that deadline covers reading its body too.
	it('does not count the refresh against the budget, and bounds the retried body', async () => {
		vi.useFakeTimers();
		const spy = vi
			.spyOn(globalThis, 'fetch')
			.mockImplementationOnce(
				() =>
					new Promise<Response>((done) =>
						setTimeout(() => done(new Response('{}', { status: 401 })), 4000)
					)
			)
			.mockImplementationOnce(
				() => new Promise<Response>((done) => setTimeout(() => done(rotated()), 10_000))
			)
			.mockImplementationOnce(
				async (_input, init) =>
					new Response(
						new ReadableStream({
							start(controller) {
								init?.signal?.addEventListener('abort', () =>
									controller.error(new DOMException('aborted', 'AbortError'))
								);
							}
						}),
						{ status: 200, headers: { 'content-type': 'application/json' } }
					)
			);
		const { event } = sessionEvent();
		const pending = handle({ event, resolve: okResolve() } as never);
		await vi.advanceTimersByTimeAsync(14_000);
		const retrySignal = () => spy.mock.calls[2]?.[1]?.signal;
		expect(retrySignal()?.aborted).toBe(false);
		await vi.advanceTimersByTimeAsync(999);
		expect(retrySignal()?.aborted).toBe(false);
		await vi.advanceTimersByTimeAsync(1);
		await expectUnavailable(await pending);
		expect(event.cookies.set).toHaveBeenCalledWith(
			'zondarr_access_token',
			'new-access',
			expect.anything()
		);
		expect(event.cookies.delete).not.toHaveBeenCalled();
	});

	it('signs in with the rotated token after a refresh', async () => {
		vi.spyOn(globalThis, 'fetch')
			.mockResolvedValueOnce(new Response('{}', { status: 401 }))
			.mockResolvedValueOnce(rotated())
			.mockResolvedValueOnce(Response.json(user));
		const { event } = sessionEvent();
		expect((await handle({ event, resolve: okResolve() } as never)).status).toBe(200);
		expect(event.locals.user).toEqual(user);
		expect(event.cookies.delete).not.toHaveBeenCalled();
	});
});

describe('session check: which requests it runs for', () => {
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

	function event(pathname: string, jar: Map<string, string>, method = 'GET') {
		const url = new URL(`http://frontend.local${pathname}`);
		return {
			request: new Request(url, {
				method,
				headers: method === 'GET' ? {} : { origin: 'http://frontend.local' }
			}),
			cookies: {
				get: vi.fn((name: string) => jar.get(name)),
				set: vi.fn((name: string, value: string) => {
					jar.set(name, value);
				}),
				delete: vi.fn(),
				parse: (header: string) => {
					const [name, value] = (header.split(';')[0] ?? '').split('=');
					return { name, value, path: '/' };
				}
			},
			locals: {} as { user?: unknown },
			url
		};
	}

	const bothCookies = () =>
		new Map([
			['zondarr_access_token', 'expired-access'],
			['zondarr_refresh_token', 'refresh-token']
		]);

	it.each([
		['GET', '/api/v1/invitations'],
		['POST', '/api/auth/refresh'],
		['POST', '/api/auth/logout'],
		['GET', '/api'],
		['GET', '/health']
	])('leaves %s %s to its route: no backend call, cookies untouched', async (method, path) => {
		const spy = vi.spyOn(globalThis, 'fetch');
		const request = event(path, bothCookies(), method);
		const resolve = okResolve();

		const response = await handle({ event: request, resolve } as never);

		expect(response.status).toBe(200);
		expect(resolve).toHaveBeenCalledOnce();
		expect(spy).not.toHaveBeenCalled();
		expect(request.locals.user).toBeNull();
		expect(request.cookies.set).not.toHaveBeenCalled();
		expect(request.cookies.delete).not.toHaveBeenCalled();
	});

	it('refreshes first when only the refresh cookie is left', async () => {
		const spy = vi
			.spyOn(globalThis, 'fetch')
			.mockResolvedValueOnce(
				new Response('{}', {
					status: 200,
					headers: [
						['set-cookie', 'zondarr_access_token=new-access; Path=/'],
						['set-cookie', 'zondarr_refresh_token=new-refresh; Path=/']
					]
				})
			)
			.mockResolvedValueOnce(Response.json(user));
		const request = event('/dashboard', new Map([['zondarr_refresh_token', 'refresh-token']]));

		const response = await handle({ event: request, resolve: okResolve() } as never);

		expect(response.status).toBe(200);
		expect(request.locals.user).toEqual(user);
		expect(spy.mock.calls.map(([input]) => String(input))).toEqual([
			'http://localhost:8000/api/auth/refresh',
			'http://localhost:8000/api/auth/me'
		]);
		expect(spy.mock.calls[0]?.[1]?.headers).toEqual({
			Cookie: 'zondarr_refresh_token=refresh-token'
		});
		expect(spy.mock.calls[1]?.[1]?.headers).toEqual({ Cookie: 'zondarr_access_token=new-access' });
		expect(request.cookies.delete).not.toHaveBeenCalled();
	});

	it('logs out when only the refresh cookie is left and the backend refuses it', async () => {
		vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(new Response('{}', { status: 401 }));
		const request = event('/dashboard', new Map([['zondarr_refresh_token', 'refresh-token']]));

		await expect(handle({ event: request, resolve: okResolve() } as never)).rejects.toMatchObject({
			status: 302,
			location: '/login'
		});
		expect(request.cookies.delete).toHaveBeenCalledTimes(2);
	});

	it('keeps the refresh cookie when the refresh fails transiently', async () => {
		vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(new Response('{}', { status: 503 }));
		const request = event('/dashboard', new Map([['zondarr_refresh_token', 'refresh-token']]));

		const response = await handle({ event: request, resolve: okResolve() } as never);

		expect(response.status).toBe(503);
		expect(request.cookies.delete).not.toHaveBeenCalled();
	});

	it('redirects a protected page to the login page without any session cookie', async () => {
		const spy = vi.spyOn(globalThis, 'fetch');
		const request = event('/dashboard', new Map());

		await expect(handle({ event: request, resolve: okResolve() } as never)).rejects.toMatchObject({
			status: 302,
			location: '/login'
		});
		expect(spy).not.toHaveBeenCalled();
		expect(request.cookies.delete).not.toHaveBeenCalled();
	});
});
