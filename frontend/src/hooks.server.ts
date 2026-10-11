import type { RequestEvent } from '@sveltejs/kit';
import { redirect } from '@sveltejs/kit';
import type { Handle } from '@sveltejs/kit/hooks';
import * as env from '$app/env/private';
import * as publicEnv from '$app/env/public';
import { backendCall, relayedCookieOptions } from '$lib/server/backend-relay';
import { foreignWriteResponse, isForeignWrite, isSecureRequest } from '$lib/server/request-origin';

const SSR_API_URL = env.INTERNAL_API_URL ?? publicEnv.PUBLIC_API_URL ?? 'http://localhost:8000';

const PUBLIC_PATHS = ['/login', '/setup', '/join', '/api', '/health'];

function isPublicPath(pathname: string): boolean {
	return PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

/** The budget, in ms, that the two `/api/auth/me` calls share; the refresh between them is not counted. */
const AUTH_ME_BUDGET_MS = 5_000;

type AuthOutcome = 'authenticated' | 'rejected' | 'transient';

/**
 * Reads the signed-in admin from the backend: `/api/auth/me`, and on a 401/403 a token refresh
 * and a second `/api/auth/me`. Only a 401/403 from the backend means the session is invalid
 * (`rejected`); a timeout, a cancelled request, a transport error or any other failure is
 * `transient`, and keeps the session cookies, including ones the refresh has just rotated.
 *
 * The refresh has no deadline: dropping its answer after the backend has rotated the token would
 * leave the browser with the consumed token, whose next use counts as a replay and revokes every
 * session of that admin (see `relayDeadline`). It still ends when the request is cancelled.
 */
async function authenticate(event: RequestEvent, accessToken: string): Promise<AuthOutcome> {
	const started = Date.now();
	const me = async (token: string, budget: number) => {
		const call = backendCall(event.request.signal);
		call.arm(budget);
		try {
			const response = await fetch(`${SSR_API_URL}/api/auth/me`, {
				headers: { Cookie: `zondarr_access_token=${token}` },
				signal: call.signal
			});
			if (!response.ok) {
				await response.body?.cancel();
				return { status: response.status, user: null };
			}
			const user: App.Locals['user'] = await response.json();
			return { status: response.status, user };
		} finally {
			call.clear();
		}
	};
	const rejection = (status: number) => status === 401 || status === 403;

	try {
		const first = await me(accessToken, AUTH_ME_BUDGET_MS);
		if (first.user) {
			event.locals.user = first.user;
			return 'authenticated';
		}
		if (!rejection(first.status)) return 'transient';

		// Access token expired — try refreshing via refresh token cookie
		const refreshToken = event.cookies.get('zondarr_refresh_token');
		if (!refreshToken) return 'rejected';
		const remaining = Math.max(0, AUTH_ME_BUDGET_MS - (Date.now() - started));
		const refreshResponse = await fetch(`${SSR_API_URL}/api/auth/refresh`, {
			method: 'POST',
			headers: { Cookie: `zondarr_refresh_token=${refreshToken}` },
			signal: event.request.signal
		});
		if (!refreshResponse.ok) {
			await refreshResponse.body?.cancel();
			return rejection(refreshResponse.status) ? 'rejected' : 'transient';
		}

		// Re-set the backend's session cookies with its own attributes, except Secure, which
		// follows this app's scheme (M16).
		for (const header of refreshResponse.headers.getSetCookie()) {
			const { name, value, ...attributes } = event.cookies.parse(header);
			const session = name === 'zondarr_access_token' || name === 'zondarr_refresh_token';
			if (session && value !== undefined) {
				event.cookies.set(name, value, relayedCookieOptions(attributes, event.url));
			}
		}
		await refreshResponse.body?.cancel();

		// Re-call /api/auth/me with the new access token, within what is left of the budget
		const newAccessToken = event.cookies.get('zondarr_access_token');
		if (!newAccessToken) return 'transient';
		const retry = await me(newAccessToken, remaining);
		if (retry.user) {
			event.locals.user = retry.user;
			return 'authenticated';
		}
		return rejection(retry.status) ? 'rejected' : 'transient';
	} catch {
		return 'transient';
	}
}

export const handle: Handle = async ({ event, resolve }) => {
	// Reject writes of any content type whose Origin is not this app's own origin, before
	// any route runs. SvelteKit itself checks only bodyless and form writes, and the
	// backend exempts its auth endpoints and requests without Origin/Referer.
	if (isForeignWrite(event.request, event.url)) {
		return foreignWriteResponse();
	}

	// Try to get user info from the access token cookie
	const accessToken = event.cookies.get('zondarr_access_token');
	const skipAuth = ['true', '1', 'yes'].includes((env.DEV_SKIP_AUTH ?? '').toLowerCase());
	// The backend could not say whether the session is valid (slow or failing), as opposed to
	// rejecting it.
	let authUnavailable = false;

	if (skipAuth && !accessToken) {
		// Dev mode: skip the API call entirely and use a synthetic admin user
		event.locals.user = {
			id: '00000000-0000-0000-0000-000000000000',
			username: 'dev-admin',
			email: null,
			auth_method: 'dev-skip',
			onboarding_required: false,
			onboarding_step: 'complete'
		};
	} else if (accessToken) {
		const outcome = await authenticate(event, accessToken);
		if (outcome !== 'authenticated') event.locals.user = null;
		if (outcome === 'rejected') {
			const secure = isSecureRequest(event.url);
			event.cookies.delete('zondarr_access_token', { path: '/', secure });
			event.cookies.delete('zondarr_refresh_token', { path: '/', secure });
		}
		authUnavailable = outcome === 'transient';
	} else {
		event.locals.user = null;
	}

	const { pathname } = event.url;
	const isOnboardingBypassPath =
		pathname.startsWith('/api') || pathname === '/health' || pathname.startsWith('/health/');

	// Enforce onboarding flow before allowing access to normal app routes.
	if (event.locals.user?.onboarding_required && pathname !== '/setup' && !isOnboardingBypassPath) {
		redirect(302, '/setup');
	}

	// Redirect authenticated users away from auth pages
	if (
		event.locals.user &&
		!event.locals.user.onboarding_required &&
		(pathname === '/login' || pathname === '/setup')
	) {
		redirect(302, '/dashboard');
	}

	// Protect non-public routes. A backend that could not answer is no evidence that the session
	// is invalid: neither grant access nor send a still signed-in admin to the login page.
	if (!event.locals.user && !isPublicPath(pathname) && pathname !== '/') {
		if (authUnavailable) {
			return new Response(JSON.stringify({ detail: 'Authentication temporarily unavailable' }), {
				status: 503,
				headers: { 'content-type': 'application/json' }
			});
		}
		redirect(302, '/login');
	}

	return resolve(event, {
		filterSerializedResponseHeaders(name) {
			return name === 'content-type' || name === 'content-length';
		}
	});
};
