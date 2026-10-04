import { describe, expect, it } from 'vitest';
import {
	HOST_HEADER as FRONT_HOST_HEADER,
	PEER_HEADER as FRONT_PEER_HEADER,
	PROTOCOL_HEADER as FRONT_PROTOCOL_HEADER
} from '../../../scripts/serve';
import {
	backendRequestHeaders,
	FRONT_HEADERS,
	relayedCookieOptions,
	relayResponseHeaders,
	relaySetCookie
} from './backend-relay';

const HTTP = new URL('http://192.168.1.10:3000/api/auth/login');
const HTTPS = new URL('https://zondarr.example.com/api/auth/login');

describe('relaySetCookie', () => {
	it.each([
		['Secure', 'a=b; HttpOnly; Max-Age=900; Path=/; SameSite=lax; Secure'],
		['a lowercase secure', 'a=b; HttpOnly; Max-Age=900; secure; Path=/; SameSite=lax'],
		['Secure with a value', 'a=b; HttpOnly; Max-Age=900; Secure=1; Path=/; SameSite=lax'],
		['no Secure', 'a=b; HttpOnly; Max-Age=900; Path=/; SameSite=lax']
	])('over http drops %s and keeps the rest in order', (_case, header) => {
		expect(relaySetCookie(header, HTTP)).toBe('a=b; HttpOnly; Max-Age=900; Path=/; SameSite=lax');
	});

	it.each([
		['Secure', 'a=b; Path=/; Expires=Wed, 21 Oct 2026 07:28:00 GMT; Secure; SameSite=Strict'],
		['no Secure', 'a=b; Path=/; Expires=Wed, 21 Oct 2026 07:28:00 GMT; SameSite=Strict']
	])('over https ends with exactly one Secure (backend had %s)', (_case, header) => {
		expect(relaySetCookie(header, HTTPS)).toBe(
			'a=b; Path=/; Expires=Wed, 21 Oct 2026 07:28:00 GMT; SameSite=Strict; Secure'
		);
	});

	it('leaves the name and value byte for byte, including a quoted empty value', () => {
		expect(relaySetCookie('zondarr_access_token=""; Max-Age=0; Path=/', HTTP)).toBe(
			'zondarr_access_token=""; Max-Age=0; Path=/'
		);
		expect(relaySetCookie('t=a%3Db.c==; Path=/', HTTPS)).toBe('t=a%3Db.c==; Path=/; Secure');
	});
});

describe('relayResponseHeaders', () => {
	it('rewrites every Set-Cookie and copies every other header', () => {
		const source = new Headers({ 'content-type': 'application/json', 'x-request-id': 'abc' });
		source.append('set-cookie', 'a=1; Path=/; Secure');
		source.append('set-cookie', 'b=2; Path=/');
		const http = relayResponseHeaders(source, HTTP);
		expect(http.getSetCookie()).toEqual(['a=1; Path=/', 'b=2; Path=/']);
		expect(http.get('content-type')).toBe('application/json');
		expect(http.get('x-request-id')).toBe('abc');
		expect(relayResponseHeaders(source, HTTPS).getSetCookie()).toEqual([
			'a=1; Path=/; Secure',
			'b=2; Path=/; Secure'
		]);
		// The backend's headers are not modified.
		expect(source.getSetCookie()).toEqual(['a=1; Path=/; Secure', 'b=2; Path=/']);
	});

	it('adds no Set-Cookie when the backend sent none', () => {
		const relayed = relayResponseHeaders(new Headers({ 'content-type': 'text/plain' }), HTTPS);
		expect(relayed.getSetCookie()).toEqual([]);
		expect(relayed.has('set-cookie')).toBe(false);
	});
});

describe('relayedCookieOptions', () => {
	// The attributes as event.cookies.parse returns them (cookie's parseSetCookie), written out
	// by hand so the tests do not import a package this app does not declare.
	it('keeps the backend attributes and takes Secure from the request origin', () => {
		// 'a=b; HttpOnly; Max-Age=900; Path=/; SameSite=lax; Secure'
		const secureBackend = {
			httpOnly: true,
			maxAge: 900,
			path: '/',
			sameSite: 'lax',
			secure: true
		} as const;
		expect(relayedCookieOptions(secureBackend, HTTP)).toEqual({ ...secureBackend, secure: false });
		// 'a=b; Path=/app; Expires=Wed, 21 Oct 2026 07:28:00 GMT; SameSite=Strict'
		const plainBackend = {
			path: '/app',
			expires: new Date('2026-10-21T07:28:00Z'),
			sameSite: 'strict'
		} as const;
		expect(relayedCookieOptions(plainBackend, HTTPS)).toEqual({
			...plainBackend,
			httpOnly: false,
			secure: true
		});
	});

	it('does not add HttpOnly or SameSite the backend left out, and defaults Path to /', () => {
		// 'a=b'
		expect(relayedCookieOptions({}, HTTP)).toEqual({
			httpOnly: false,
			path: '/',
			sameSite: false,
			secure: false
		});
	});
});

describe('backendRequestHeaders', () => {
	it('names exactly the headers scripts/serve.ts sets', () => {
		expect([...FRONT_HEADERS].sort()).toEqual(
			[FRONT_PROTOCOL_HEADER, FRONT_HOST_HEADER, FRONT_PEER_HEADER].sort()
		);
	});

	it('drops the front headers, forwarded headers and hop-by-hop headers, in any case', () => {
		const source = new Headers({
			Origin: 'http://192.168.1.10:3000',
			Referer: 'http://192.168.1.10:3000/users',
			Cookie: 'zondarr_access_token=abc',
			'Content-Type': 'application/json',
			'X-Zondarr-Origin-Proto': 'https',
			'x-zondarr-origin-host': 'evil.test',
			'x-zondarr-peer': '203.0.113.9',
			'X-Forwarded-For': '203.0.113.9',
			'X-Forwarded-Proto': 'https',
			'X-Forwarded-Host': 'evil.test',
			'X-Forwarded-Port': '443',
			'X-Forwarded-Prefix': '/evil',
			Forwarded: 'for=203.0.113.9',
			Host: 'evil.test',
			Connection: 'keep-alive',
			'Keep-Alive': 'timeout=5',
			'Transfer-Encoding': 'chunked',
			Upgrade: 'websocket'
		});
		expect([...backendRequestHeaders(source).entries()]).toEqual([
			['content-type', 'application/json'],
			['cookie', 'zondarr_access_token=abc'],
			['origin', 'http://192.168.1.10:3000'],
			['referer', 'http://192.168.1.10:3000/users']
		]);
	});

	it('drops extra headers a caller names', () => {
		const source = new Headers({ 'content-length': '12', 'content-type': 'application/json' });
		expect([...backendRequestHeaders(source, ['Content-Length']).keys()]).toEqual(['content-type']);
	});
});
