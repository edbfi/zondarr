/**
 * What the frontend passes on between the browser and the backend: the `/api/*` proxy, the
 * setup endpoint and the session refresh in `hooks.server.ts`.
 *
 * Requests reach the backend without the headers this app's front sets (`scripts/serve.ts`) and
 * without client-supplied `X-Forwarded-*` and `Forwarded` headers: the backend reads none of them
 * today, and none of them is trustworthy by the time it gets there.
 *
 * Cookies the backend sets reach the browser through the frontend, so their `Secure` attribute
 * follows the app's own scheme (`event.url`), as for the cookies the frontend sets itself. The
 * backend only knows its own `SECURE_COOKIES` setting, and browsers refuse `Secure` cookies over
 * plain HTTP outside loopback.
 *
 * @module $lib/server/backend-relay
 */
import type { Cookies } from '@sveltejs/kit';
import { isSecureRequest } from './request-origin';

/** The headers `scripts/serve.ts` sets on every request it fronts. */
export const FRONT_HEADERS = [
	'x-zondarr-origin-proto',
	'x-zondarr-origin-host',
	'x-zondarr-peer'
] as const;

const HOP_BY_HOP = ['host', 'connection', 'keep-alive', 'transfer-encoding', 'upgrade'];
const NEVER_FORWARDED = new Set<string>([...HOP_BY_HOP, ...FRONT_HEADERS, 'forwarded']);

/**
 * The request headers to send to the backend: everything the client sent (including `Origin`,
 * `Referer` and `Cookie`, which the backend checks) except hop-by-hop headers, the front's
 * headers, `Forwarded`, every `X-Forwarded-*` header and any `extra` header the caller names.
 */
export function backendRequestHeaders(source: Headers, extra: readonly string[] = []): Headers {
	const dropped = new Set(extra.map((name) => name.toLowerCase()));
	const headers = new Headers();
	for (const [name, value] of source) {
		// Headers iterates lowercase names.
		if (NEVER_FORWARDED.has(name) || name.startsWith('x-forwarded-') || dropped.has(name)) continue;
		headers.append(name, value);
	}
	return headers;
}

type SetCookieAttributes = Omit<ReturnType<Cookies['parse']>, 'name' | 'value'>;

/**
 * A backend `Set-Cookie` header as the browser should get it: `Secure` exactly when the app's
 * origin is `https`, everything else (name, value and the other attributes, in order) unchanged.
 */
export function relaySetCookie(header: string, url: URL): string {
	const [pair = '', ...attributes] = header.split(';');
	const kept = attributes
		.map((attribute) => attribute.trim())
		.filter((attribute) => attribute && attribute.split('=')[0]?.trim().toLowerCase() !== 'secure');
	if (isSecureRequest(url)) kept.push('Secure');
	return [pair.trim(), ...kept].join('; ');
}

/** A copy of the backend's response headers with every `Set-Cookie` passed through `relaySetCookie`. */
export function relayResponseHeaders(source: Headers, url: URL): Headers {
	const headers = new Headers(source);
	headers.delete('set-cookie');
	for (const cookie of source.getSetCookie()) {
		headers.append('set-cookie', relaySetCookie(cookie, url));
	}
	return headers;
}

/**
 * Options for `event.cookies.set` that re-set a backend cookie parsed with `event.cookies.parse`:
 * the backend's attributes, `Secure` from the app's origin, and no SvelteKit default the backend
 * did not ask for (`HttpOnly`, `SameSite`). A missing `Path` becomes `/`, as SvelteKit requires
 * one and the backend's default path would name its own endpoint.
 */
export function relayedCookieOptions(attributes: SetCookieAttributes, url: URL) {
	return {
		...attributes,
		path: attributes.path ?? '/',
		httpOnly: attributes.httpOnly ?? false,
		sameSite: attributes.sameSite ?? false,
		secure: isSecureRequest(url)
	};
}
