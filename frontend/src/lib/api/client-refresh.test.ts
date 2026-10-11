/**
 * Session refresh on a 401 in the browser, for the default client, scoped clients (load
 * functions) and the raw-fetch wrappers: only a session the backend refuses leads to the login
 * page, and on the server nothing refreshes.
 *
 * @module $lib/api/client-refresh.test
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('$app/env/public', () => ({ PUBLIC_API_URL: 'http://backend.test' }));

const ME = 'http://backend.test/api/auth/me';
const REFRESH = 'http://backend.test/api/auth/refresh';
const SETTINGS = 'http://backend.test/api/v1/settings';
const SECURE_COOKIES = 'http://backend.test/api/v1/settings/secure-cookies';
const PASSWORD = 'http://backend.test/api/auth/me/change-password';
const USERS = 'http://backend.test/api/v1/users';

type Answer = Response | Error;

const urlOf = (input: RequestInfo | URL) => (input instanceof Request ? input.url : String(input));

/** A fake fetch: `me` answers in turn for `url` (default /api/auth/me), `refresh` for the refresh. */
function backend(me: Answer[], refresh: Answer[], url = ME) {
	return vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
		const called = urlOf(input);
		const queue = called === url ? me : called === REFRESH ? refresh : [];
		const answer = queue.shift();
		if (answer === undefined) throw new Error(`unexpected call to ${called}`);
		if (answer instanceof Error) throw answer;
		return answer;
	});
}

/** A fetch mock as the `typeof fetch` that load functions pass (Bun's type adds members). */
const asFetch = (mock: ReturnType<typeof backend>) => mock as unknown as typeof fetch;

const unauthorized = () => new Response('{}', { status: 401 });

/** Load a fresh client module (its refresh promise is module state) on top of `fetchMock`. */
async function loadClient(fetchMock: ReturnType<typeof backend>) {
	vi.stubGlobal('fetch', fetchMock);
	vi.resetModules();
	return (await import('./client')).api;
}

describe('refresh after a 401', () => {
	let location: { pathname: string; href: string; origin: string };

	beforeEach(() => {
		location = {
			pathname: '/dashboard',
			href: 'http://frontend.test/dashboard',
			origin: 'http://frontend.test'
		};
		vi.stubGlobal('location', location);
	});

	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it('retries the request once the refresh succeeds', async () => {
		const fetchMock = backend(
			[unauthorized(), Response.json({ username: 'admin' })],
			[new Response('{}', { status: 200 })]
		);
		const api = await loadClient(fetchMock);

		const { response } = await api.GET('/api/auth/me');

		expect(response.status).toBe(200);
		expect(location.href).toBe('http://frontend.test/dashboard');
	});

	it.each([
		['a 401', 401],
		['a 403', 403]
	])(
		'goes to the login page when the backend answers the refresh with %s',
		async (_label, status) => {
			const api = await loadClient(backend([unauthorized()], [new Response('{}', { status })]));

			const { response } = await api.GET('/api/auth/me');

			expect(response.status).toBe(401);
			expect(location.href).toBe('/login');
		}
	);

	it.each([
		['a 503', new Response('{}', { status: 503 })],
		['a 502 from the relay', new Response('{}', { status: 502 })],
		['a 504 from the relay', new Response('{}', { status: 504 })],
		['a network error', new TypeError('Failed to fetch')]
	])('stays on the page and returns the 401 after %s', async (_label, answer) => {
		const fetchMock = backend([unauthorized()], [answer]);
		const api = await loadClient(fetchMock);

		const { response } = await api.GET('/api/auth/me');

		expect(response.status).toBe(401);
		expect(location.href).toBe('http://frontend.test/dashboard');
		expect(fetchMock).toHaveBeenCalledTimes(2);
	});

	it('shares one refresh between concurrent 401s', async () => {
		let refreshed = false;
		let finishRefresh: (response: Response) => void = () => {};
		const pendingRefresh = new Promise<Response>((done) => {
			finishRefresh = (response) => {
				refreshed = true;
				done(response);
			};
		});
		const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
			const url = input instanceof Request ? input.url : String(input);
			if (url === REFRESH) return pendingRefresh;
			return refreshed ? Response.json({ username: 'admin' }) : unauthorized();
		});
		vi.stubGlobal('fetch', fetchMock);
		vi.resetModules();
		const { api } = await import('./client');

		const both = Promise.all([api.GET('/api/auth/me'), api.GET('/api/auth/me')]);
		await vi.waitFor(() => {
			expect(fetchMock.mock.calls.filter(([input]) => String(input) === REFRESH)).toHaveLength(1);
		});
		finishRefresh(new Response('{}', { status: 200 }));
		const results = await both;

		expect(results.map(({ response }) => response.status)).toEqual([200, 200]);
		expect(fetchMock.mock.calls.filter(([input]) => String(input) === REFRESH)).toHaveLength(1);
	});

	it('refreshes and retries for a scoped client (load functions)', async () => {
		const globalFetch = backend([], [new Response('{}', { status: 200 })]);
		const loadFetch = backend(
			[unauthorized(), Response.json({ items: [], total: 0, page: 1, page_size: 50 })],
			[],
			USERS
		);
		vi.stubGlobal('fetch', globalFetch);
		vi.resetModules();
		const { createScopedClient } = await import('./client');

		const { response } = await createScopedClient(asFetch(loadFetch)).GET('/api/v1/users');

		expect(response.status).toBe(200);
		expect(loadFetch).toHaveBeenCalledTimes(2);
		expect(globalFetch.mock.calls.map(([input]) => urlOf(input))).toEqual([REFRESH]);
		expect(location.href).toBe('http://frontend.test/dashboard');
	});

	it('refreshes and retries for a raw wrapper with a load fetch', async () => {
		const settings = { csrf_origin: { value: null, is_locked: false } };
		const globalFetch = backend([], [new Response('{}', { status: 200 })]);
		const loadFetch = backend([unauthorized(), Response.json(settings)], [], SETTINGS);
		vi.stubGlobal('fetch', globalFetch);
		vi.resetModules();
		const { getAllSettings } = await import('./client');

		const result = await getAllSettings(asFetch(loadFetch));

		expect(result).toEqual({ data: settings });
		expect(loadFetch).toHaveBeenCalledTimes(2);
	});

	it('retries a raw write with its body after the refresh', async () => {
		const updated = { secure_cookies: true, is_locked: false };
		const fetchMock = backend(
			[unauthorized(), Response.json(updated)],
			[new Response('{}', { status: 200 })],
			SECURE_COOKIES
		);
		vi.stubGlobal('fetch', fetchMock);
		vi.resetModules();
		const { setSecureCookies } = await import('./client');

		const result = await setSecureCookies(true);

		expect(result).toEqual({ data: updated });
		const writes = fetchMock.mock.calls.filter(([input]) => urlOf(input) === SECURE_COOKIES);
		expect(writes.map(([, init]) => init?.body)).toEqual([
			'{"secure_cookies":true}',
			'{"secure_cookies":true}'
		]);
	});

	it('keeps the page and returns the error when a raw wrapper hits a transient refresh failure', async () => {
		const fetchMock = backend(
			[new Response('{"detail":"expired"}', { status: 401 })],
			[new Response('{}', { status: 503 })],
			PASSWORD
		);
		vi.stubGlobal('fetch', fetchMock);
		vi.resetModules();
		const { changePassword } = await import('./auth');

		const result = await changePassword({ current_password: 'a', new_password: 'b' });

		expect(result).toEqual({ error: { detail: 'expired' } });
		expect(location.href).toBe('http://frontend.test/dashboard');
	});

	it('does not refresh on the server: the hook already did for the page request', async () => {
		const loadFetch = backend([unauthorized()], [], USERS);
		const globalFetch = vi.fn();
		vi.stubGlobal('fetch', globalFetch);
		vi.stubGlobal('window', undefined);
		vi.resetModules();
		const { createScopedClient } = await import('./client');

		const { response } = await createScopedClient(asFetch(loadFetch)).GET('/api/v1/users');

		expect(response.status).toBe(401);
		expect(loadFetch).toHaveBeenCalledOnce();
		expect(globalFetch).not.toHaveBeenCalled();
	});
});
