import { redirect } from '@sveltejs/kit';
import type { Handle } from '@sveltejs/kit/hooks';
import * as env from '$app/env/private';
import * as publicEnv from '$app/env/public';
import { relayedCookieOptions } from '$lib/server/backend-relay';
import { foreignWriteResponse, isForeignWrite, isSecureRequest } from '$lib/server/request-origin';

const SSR_API_URL = env.INTERNAL_API_URL ?? publicEnv.PUBLIC_API_URL ?? 'http://localhost:8000';

const PUBLIC_PATHS = ['/login', '/setup', '/join', '/api', '/health'];

function isPublicPath(pathname: string): boolean {
	return PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`));
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
		const controller = new AbortController();
		const timeout = setTimeout(() => controller.abort(), 2000);
		try {
			const response = await fetch(`${SSR_API_URL}/api/auth/me`, {
				headers: { Cookie: `zondarr_access_token=${accessToken}` },
				signal: controller.signal
			});
			if (response.ok) {
				const user: App.Locals['user'] = await response.json();
				event.locals.user = user;
			} else if (response.status === 401 || response.status === 403) {
				// Access token expired — try refreshing via refresh token cookie
				const refreshToken = event.cookies.get('zondarr_refresh_token');
				let refreshed = false;

				if (refreshToken) {
					try {
						const refreshResponse = await fetch(`${SSR_API_URL}/api/auth/refresh`, {
							method: 'POST',
							headers: {
								Cookie: `zondarr_refresh_token=${refreshToken}`
							}
						});

						if (refreshResponse.ok) {
							// Re-set the backend's session cookies with its own attributes, except
							// Secure, which follows this app's scheme (M16).
							for (const header of refreshResponse.headers.getSetCookie()) {
								const { name, value, ...attributes } = event.cookies.parse(header);
								const session = name === 'zondarr_access_token' || name === 'zondarr_refresh_token';
								if (session && value !== undefined) {
									event.cookies.set(name, value, relayedCookieOptions(attributes, event.url));
								}
							}

							// Re-call /api/auth/me with the new access token
							const newAccessToken = event.cookies.get('zondarr_access_token');
							if (newAccessToken) {
								const retryResponse = await fetch(`${SSR_API_URL}/api/auth/me`, {
									headers: { Cookie: `zondarr_access_token=${newAccessToken}` }
								});
								if (retryResponse.ok) {
									const user: App.Locals['user'] = await retryResponse.json();
									event.locals.user = user;
									refreshed = true;
								}
							}
						}
					} catch {
						// Refresh failed — fall through to clear cookies
					}
				}

				if (!refreshed) {
					const secure = isSecureRequest(event.url);
					event.cookies.delete('zondarr_access_token', { path: '/', secure });
					event.cookies.delete('zondarr_refresh_token', { path: '/', secure });
					event.locals.user = null;
				}
			} else {
				// Transient backend error (500/503) — keep cookie, skip user
				event.locals.user = null;
			}
		} catch {
			event.locals.user = null;
		} finally {
			clearTimeout(timeout);
		}
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

	// Protect non-public routes
	if (!event.locals.user && !isPublicPath(pathname) && pathname !== '/') {
		redirect(302, '/login');
	}

	return resolve(event, {
		filterSerializedResponseHeaders(name) {
			return name === 'content-type' || name === 'content-length';
		}
	});
};
