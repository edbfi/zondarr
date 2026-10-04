import { afterEach, describe, expect, it, vi } from 'vitest';
import { POST } from './+server';

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
