import { parseSetCookie } from 'cookie';
import { describe, expect, it } from 'vitest';
import { relayedCookieOptions, relayResponseHeaders, relaySetCookie } from './backend-relay';

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
	const options = (header: string, url: URL) => {
		const { name: _name, value: _value, ...attributes } = parseSetCookie(header);
		return relayedCookieOptions(attributes, url);
	};

	it('keeps the backend attributes and takes Secure from the request origin', () => {
		const header = 'a=b; HttpOnly; Max-Age=900; Path=/; SameSite=lax; Secure';
		expect(options(header, HTTP)).toEqual({
			httpOnly: true,
			maxAge: 900,
			path: '/',
			sameSite: 'lax',
			secure: false
		});
		expect(options('a=b; HttpOnly; Max-Age=900; Path=/; SameSite=lax', HTTPS)).toEqual({
			httpOnly: true,
			maxAge: 900,
			path: '/',
			sameSite: 'lax',
			secure: true
		});
	});

	it('does not add HttpOnly or SameSite the backend left out, and defaults Path to /', () => {
		expect(options('a=b', HTTP)).toEqual({
			httpOnly: false,
			path: '/',
			sameSite: false,
			secure: false
		});
	});
});
