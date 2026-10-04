/**
 * What the frontend passes on between the browser and the backend: the `/api/*` proxy, the
 * setup endpoint and the session refresh in `hooks.server.ts`.
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
