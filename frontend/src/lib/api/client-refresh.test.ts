/**
 * The API client's refresh on a 401: only a session the backend refuses leads to the login page.
 *
 * @module $lib/api/client-refresh.test
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('$app/env/public', () => ({ PUBLIC_API_URL: 'http://backend.test' }));

const ME = 'http://backend.test/api/auth/me';
const REFRESH = 'http://backend.test/api/auth/refresh';

type Answer = Response | Error;

/** A fake fetch: `me` answers in turn for /api/auth/me, `refresh` for the refresh. */
function backend(me: Answer[], refresh: Answer[]) {
	return vi.fn(async (input: RequestInfo | URL) => {
		const url = input instanceof Request ? input.url : String(input);
		const queue = url === ME ? me : url === REFRESH ? refresh : [];
		const answer = queue.shift();
		if (answer === undefined) throw new Error(`unexpected call to ${url}`);
		if (answer instanceof Error) throw answer;
		return answer;
	});
}

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
});
