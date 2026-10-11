/**
 * Session refresh for backend calls made in the browser.
 *
 * `withSessionRefresh(fetch)` wraps a fetch function: when the backend's access-token check
 * answers a call with 401, it refreshes the session once for the whole page (concurrent 401s share one refresh) and retries the call once.
 * The default API client, every scoped client (load functions) and the raw-fetch wrappers of
 * authenticated endpoints use it, since the server hook leaves `/api/*` to the relay.
 *
 * On the server (SSR of a universal load, or a server load) the wrapper only passes the call
 * through: the hook has already checked, and if needed refreshed, the session of the page request,
 * and SvelteKit's server `fetch` sends the cookies the hook set. A second refresh there would rotate
 * the same refresh token again.
 *
 * @module $lib/api/session-refresh
 */

import * as env from '$app/env/public';

const API_BASE_URL = env.PUBLIC_API_URL ?? '';

/**
 * What a token refresh came to: `ok` (new session cookies are set), `rejected` (the backend
 * refused the session with a 401/403: sign in again) or `transient` (no answer, or another
 * failure: the session may still be valid, so keep it and let the caller retry later).
 */
export type RefreshOutcome = 'ok' | 'rejected' | 'transient';

/** A fetch function: the global `fetch`, SvelteKit's load `fetch`, or a wrapper of either. */
export type Fetch = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

/** Auth endpoints whose 401 is not about the session, so it never triggers a refresh. */
const NO_REFRESH_ENDPOINTS = ['/api/auth/refresh', '/api/auth/login', '/api/auth/setup'];

/** Pages without a session to refresh; a 401 there must not loop back to the login page. */
const NO_REFRESH_PAGES = ['/login', '/join', '/setup'];

// One refresh at a time for the page. Browser only: the wrapper never refreshes on the server, so
// this module state is never shared between server requests.
let refreshPromise: Promise<RefreshOutcome> | null = null;

async function attemptTokenRefresh(): Promise<RefreshOutcome> {
	try {
		const response = await globalThis.fetch(`${API_BASE_URL}/api/auth/refresh`, {
			method: 'POST',
			credentials: 'include'
		});
		await response.body?.cancel();
		if (response.ok) return 'ok';
		return response.status === 401 || response.status === 403 ? 'rejected' : 'transient';
	} catch {
		return 'transient';
	}
}

/** Refresh the session, joining a refresh that is already running. */
export function refreshSession(): Promise<RefreshOutcome> {
	refreshPromise ??= attemptTokenRefresh().finally(() => {
		refreshPromise = null;
	});
	return refreshPromise;
}

/**
 * Whether a 401 comes from the backend's access-token check (missing, invalid or expired token,
 * revoked session), which answers `error_code: "HTTP_ERROR"`. An endpoint's own 401 for wrong
 * input (a wrong current password, a wrong TOTP code) has a specific code and is no reason to
 * refresh. The body is read from a copy, so the caller can still read the response.
 */
async function isSessionFailure(response: Response): Promise<boolean> {
	try {
		const body: unknown = await response.clone().json();
		return (
			typeof body === 'object' &&
			body !== null &&
			'error_code' in body &&
			body.error_code === 'HTTP_ERROR'
		);
	} catch {
		return false;
	}
}

function pathOf(input: RequestInfo | URL): string {
	const href = input instanceof Request ? input.url : input instanceof URL ? input.href : input;
	return new URL(href, window.location.origin).pathname;
}

/**
 * Wrap `baseFetch` (default: the global `fetch`, looked up per call) so that a 401 from the
 * access-token check in the browser refreshes the session and retries the call once. Any other 401
 * is returned as it is. Only a session the backend refuses leads to the login page; after a
 * transient failure the caller gets the original 401 and keeps its cookies.
 */
export function withSessionRefresh(baseFetch?: Fetch): Fetch {
	const send: Fetch = baseFetch ?? ((input, init) => globalThis.fetch(input, init));
	return async (input, init) => {
		if (typeof window === 'undefined') return send(input, init);

		// Keep a copy of a Request now: sending it consumes its body.
		const retry: Parameters<Fetch> =
			input instanceof Request ? [input.clone(), init] : [input, init];
		const response = await send(input, init);

		if (
			response.status !== 401 ||
			NO_REFRESH_PAGES.some((page) => window.location.pathname.startsWith(page))
		) {
			return response;
		}

		const path = pathOf(input);
		if (NO_REFRESH_ENDPOINTS.some((ep) => path === ep || path.startsWith(`${ep}/`))) {
			window.location.href = '/login';
			return response;
		}
		if (!(await isSessionFailure(response))) return response;

		const outcome = await refreshSession();
		// The 401's body was read from a copy; the unread original is dropped without awaiting a
		// cancel, which can hang once the copy has been read.
		if (outcome === 'ok') return send(...retry);
		if (outcome === 'rejected') window.location.href = '/login';
		return response;
	};
}
