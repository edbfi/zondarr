import { afterEach, describe, expect, it, vi } from 'vitest';
import { BACKEND_DEADLINE_MS } from '$lib/server/backend-relay';
import { GET, POST } from './+server';

type PostHandlerEvent = Parameters<typeof POST>[0];

function makeEvent(request: Request, path: string): PostHandlerEvent {
	return {
		request,
		url: new URL(request.url),
		params: { path }
	} as PostHandlerEvent;
}

describe('API proxy route', () => {
	afterEach(() => {
		vi.restoreAllMocks();
	});

	it('forwards Origin and Referer while stripping hop-by-hop headers', async () => {
		const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
			new Response(JSON.stringify({ ok: true }), {
				status: 201,
				headers: { 'content-type': 'application/json' }
			})
		);

		const request = new Request(
			'http://frontend.local/api/v1/settings/csrf-origin/test?from=setup',
			{
				method: 'POST',
				headers: {
					'content-type': 'application/json',
					origin: 'https://app.example.com',
					referer: 'https://app.example.com/setup',
					host: 'frontend.local',
					connection: 'keep-alive',
					'keep-alive': 'timeout=5',
					'transfer-encoding': 'chunked',
					upgrade: 'websocket'
				},
				body: JSON.stringify({ origin: 'https://app.example.com' })
			}
		);

		const response = await POST(makeEvent(request, 'v1/settings/csrf-origin/test'));

		expect(fetchSpy).toHaveBeenCalledTimes(1);
		const [upstream, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
		expect(upstream).toBe('http://localhost:8000/api/v1/settings/csrf-origin/test?from=setup');
		expect(init.method).toBe('POST');
		expect(init.body).toBeDefined();

		const forwarded = new Headers(init.headers);
		expect(forwarded.get('origin')).toBe('https://app.example.com');
		expect(forwarded.get('referer')).toBe('https://app.example.com/setup');
		expect(forwarded.has('host')).toBe(false);
		expect(forwarded.has('connection')).toBe(false);
		expect(forwarded.has('keep-alive')).toBe(false);
		expect(forwarded.has('transfer-encoding')).toBe(false);
		expect(forwarded.has('upgrade')).toBe(false);

		expect(response.status).toBe(201);
		await expect(response.json()).resolves.toEqual({ ok: true });
	});

	describe.each([
		['http:', false],
		['https:', true]
	])('relays backend cookies over %s with secure: %s (M16)', (protocol, secure) => {
		const backendCookies = [
			'zondarr_access_token=new-access; HttpOnly; Max-Age=900; Path=/; SameSite=lax; Secure',
			'zondarr_refresh_token=new-refresh; HttpOnly; Max-Age=604800; Path=/; SameSite=lax',
			'zondarr_access_token=""; HttpOnly; Max-Age=0; Path=/; SameSite=lax'
		];
		const relayed = (secureFlag: boolean) => [
			`zondarr_access_token=new-access; HttpOnly; Max-Age=900; Path=/; SameSite=lax${secureFlag ? '; Secure' : ''}`,
			`zondarr_refresh_token=new-refresh; HttpOnly; Max-Age=604800; Path=/; SameSite=lax${secureFlag ? '; Secure' : ''}`,
			`zondarr_access_token=""; HttpOnly; Max-Age=0; Path=/; SameSite=lax${secureFlag ? '; Secure' : ''}`
		];

		it.each([
			['a buffered', 'application/json'],
			['an event-stream', 'text/event-stream']
		])('in %s response', async (_kind, contentType) => {
			const upstream = new Headers({ 'content-type': contentType, 'x-request-id': 'abc' });
			for (const cookie of backendCookies) upstream.append('set-cookie', cookie);
			vi.spyOn(globalThis, 'fetch').mockResolvedValue(
				new Response('{}', { status: 200, headers: upstream })
			);
			const request = new Request(`${protocol}//frontend.local/api/auth/login`, {
				method: 'POST',
				headers: { 'content-type': 'application/json', origin: `${protocol}//frontend.local` },
				body: '{}'
			});

			const response = await POST(makeEvent(request, 'auth/login'));

			expect(response.headers.getSetCookie()).toEqual(relayed(secure));
			expect(response.headers.get('content-type')).toBe(contentType);
			expect(response.headers.get('x-request-id')).toBe('abc');
		});
	});

	it.each([
		['GET', undefined],
		['POST', '{}']
	])(
		'does not pass front, forwarded or hop-by-hop headers to the backend on %s (M16)',
		async (method, body) => {
			const fetchSpy = vi
				.spyOn(globalThis, 'fetch')
				.mockResolvedValue(new Response('{}', { status: 200 }));
			const request = new Request('http://frontend.local/api/v1/users?page=2', {
				method,
				headers: {
					'content-type': 'application/json',
					origin: 'http://frontend.local',
					referer: 'http://frontend.local/users',
					cookie: 'zondarr_access_token=abc',
					authorization: 'Bearer abc',
					accept: 'application/json',
					'x-zondarr-origin-proto': 'https',
					'x-zondarr-origin-host': 'evil.test',
					'x-zondarr-peer': '203.0.113.9',
					'x-forwarded-for': '203.0.113.9',
					'x-forwarded-proto': 'https',
					'x-forwarded-host': 'evil.test',
					'x-forwarded-port': '443',
					forwarded: 'for=203.0.113.9;proto=https;host=evil.test',
					connection: 'keep-alive'
				},
				body
			});

			await POST(makeEvent(request, 'v1/users'));

			const forwarded = new Headers((fetchSpy.mock.calls[0] as [string, RequestInit])[1].headers);
			expect([...forwarded.keys()].sort()).toEqual([
				'accept',
				'authorization',
				'content-type',
				'cookie',
				'origin',
				'referer'
			]);
		}
	);
});

describe('API proxy deadlines and cancellation', () => {
	afterEach(() => {
		vi.useRealTimers();
		vi.restoreAllMocks();
	});

	function relayEvent(method: string, path: string, client = new AbortController()) {
		const request = new Request(`http://frontend.local/api/${path}`, {
			method,
			signal: client.signal,
			...(method === 'GET' ? {} : { body: '{}', headers: { 'content-type': 'application/json' } })
		});
		return makeEvent(request, path);
	}

	/** A backend that never sends headers: the fetch settles only when its signal aborts. */
	function stalledBackend() {
		return vi.spyOn(globalThis, 'fetch').mockImplementation(
			(_input, init) =>
				new Promise<Response>((_resolve, reject) => {
					init?.signal?.addEventListener('abort', () =>
						reject(new DOMException('aborted', 'AbortError'))
					);
				})
		);
	}

	/** A backend that sends headers, then a body that ends only when the call's signal aborts. */
	function stalledBody(contentType = 'application/json') {
		return vi.spyOn(globalThis, 'fetch').mockImplementation(
			async (_input, init) =>
				new Response(
					new ReadableStream({
						start(controller) {
							init?.signal?.addEventListener('abort', () =>
								controller.error(new DOMException('aborted', 'AbortError'))
							);
						}
					}),
					{ status: 200, headers: { 'content-type': contentType } }
				)
		);
	}

	const signalOf = (spy: ReturnType<typeof stalledBackend>) => spy.mock.calls[0]?.[1]?.signal;

	it('answers 504 when the backend sends no headers within the deadline', async () => {
		vi.useFakeTimers();
		stalledBackend();
		const pending = GET(relayEvent('GET', 'v1/servers'));
		await vi.advanceTimersByTimeAsync(BACKEND_DEADLINE_MS);
		const response = await pending;
		expect(response.status).toBe(504);
		expect(await response.json()).toEqual({ detail: 'Backend timed out' });
	});

	it('keeps the same deadline, not a new one, while it reads a buffered answer', async () => {
		vi.useFakeTimers();
		const headersAfter = 90_000;
		const spy = vi.spyOn(globalThis, 'fetch').mockImplementation(
			(_input, init) =>
				new Promise<Response>((done) =>
					setTimeout(
						() =>
							done(
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
							),
						headersAfter
					)
				)
		);
		const pending = GET(relayEvent('GET', 'v1/users'));
		await vi.advanceTimersByTimeAsync(BACKEND_DEADLINE_MS - 1);
		expect(signalOf(spy)?.aborted).toBe(false);
		await vi.advanceTimersByTimeAsync(1);
		expect((await pending).status).toBe(504);
	});

	it('cancels the backend call and answers 502, not 504, when the client goes away', async () => {
		const client = new AbortController();
		const spy = stalledBackend();
		const pending = GET(relayEvent('GET', 'v1/users', client));
		client.abort();
		expect((await pending).status).toBe(502);
		expect(signalOf(spy)?.aborted).toBe(true);
	});

	it('gives an established event stream no deadline, and ends it with the request', async () => {
		vi.useFakeTimers();
		const client = new AbortController();
		const spy = stalledBody('text/event-stream');
		const response = await GET(relayEvent('GET', 'v1/logs/stream', client));
		expect(response.status).toBe(200);
		await vi.advanceTimersByTimeAsync(BACKEND_DEADLINE_MS * 2);
		expect(signalOf(spy)?.aborted).toBe(false);
		client.abort();
		expect(signalOf(spy)?.aborted).toBe(true);
	});

	it.each([
		'v1/servers',
		'v1/servers/4b6f0c8e-0000-4000-8000-000000000001/sync',
		'v1/servers/4b6f0c8e-0000-4000-8000-000000000001/sync-libraries/',
		'v1/join/ABC123'
	])('waits for the answer to POST %s without a deadline', async (path) => {
		vi.useFakeTimers();
		const client = new AbortController();
		const spy = stalledBackend();
		const pending = POST(relayEvent('POST', path, client));
		await vi.advanceTimersByTimeAsync(BACKEND_DEADLINE_MS * 2);
		expect(signalOf(spy)?.aborted).toBe(false);
		client.abort();
		expect((await pending).status).toBe(502);
	});

	it('gives the buffered answer of a long operation the deadline', async () => {
		vi.useFakeTimers();
		stalledBody();
		const pending = POST(relayEvent('POST', 'v1/servers/4b6f0c8e/sync'));
		await vi.advanceTimersByTimeAsync(BACKEND_DEADLINE_MS);
		expect((await pending).status).toBe(504);
	});

	// Dropping a refresh answer after the backend rotated the token would leave the browser with the
	// consumed token, whose next use the backend treats as a replay (it revokes every session).
	it('never times out a token refresh, answer included', async () => {
		vi.useFakeTimers();
		const client = new AbortController();
		const spy = stalledBody();
		const pending = POST(relayEvent('POST', 'auth/refresh', client));
		await vi.advanceTimersByTimeAsync(BACKEND_DEADLINE_MS * 2);
		expect(signalOf(spy)?.aborted).toBe(false);
		client.abort();
		expect((await pending).status).toBe(502);
	});
});
