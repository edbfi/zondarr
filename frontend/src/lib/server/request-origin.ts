/**
 * Request-origin helpers for the server hook.
 *
 * `url` is always `event.url`: SvelteKit builds it from the app's own origin (the
 * front's `ORIGIN`, a trusted proxy's protocol and host headers, or the adapter's
 * default of `https` plus `Host`). Nothing here reads the `Host` header directly.
 *
 * @module $lib/server/request-origin
 */

const WRITE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

/** Error code of the 403 that `isForeignWrite` leads to, distinct from Kit's and the backend's. */
export const FRONTEND_ORIGIN_MISMATCH = 'FRONTEND_ORIGIN_MISMATCH';

/**
 * True for a write (`POST`, `PUT`, `PATCH`, `DELETE`) of any content type whose `Origin`
 * header is not exactly the app's own origin. A missing `Origin` or `Origin: null`
 * counts as foreign, as in SvelteKit's own check for bodyless and form writes.
 */
export function isForeignWrite(request: Request, url: URL): boolean {
	if (!WRITE_METHODS.has(request.method)) return false;
	return request.headers.get('origin') !== url.origin;
}

/** The 403 answer for a foreign write. */
export function foreignWriteResponse(): Response {
	return Response.json(
		{
			detail: 'Cross-origin write rejected: the Origin header does not match this app',
			error_code: FRONTEND_ORIGIN_MISMATCH
		},
		{ status: 403 }
	);
}
