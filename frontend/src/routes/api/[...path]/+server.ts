import * as env from '$app/env/private';
import * as publicEnv from '$app/env/public';
import { backendRequestHeaders, relayResponseHeaders } from '$lib/server/backend-relay';
import type { RequestHandler } from './$types';

const INTERNAL_API_URL =
	env.INTERNAL_API_URL ?? publicEnv.PUBLIC_API_URL ?? 'http://localhost:8000';

const handler: RequestHandler = async ({ request, url, params }) => {
	const path = params.path;
	const upstream = `${INTERNAL_API_URL}/api/${path}${url.search}`;

	// Origin and Referer pass through: the backend validates them (core/csrf.py). Hop-by-hop
	// headers, the front's own headers and client-sent forwarded headers do not (M16).
	const headers = backendRequestHeaders(request.headers);

	const hasBody = !['GET', 'HEAD'].includes(request.method);

	try {
		const response = await fetch(upstream, {
			method: request.method,
			headers,
			body: hasBody ? request.body : undefined,
			// @ts-expect-error -- Bun supports duplex streaming
			duplex: hasBody ? 'half' : undefined,
			redirect: 'manual'
		});

		// SSE responses must stream; buffer everything else to avoid
		// ReadableStream being consumed during SvelteKit's SSR cloning.
		const isEventStream = response.headers.get('content-type')?.includes('text/event-stream');
		// Backend cookies get Secure from this app's own scheme, not the backend's setting (M16).
		const responseHeaders = relayResponseHeaders(response.headers, url);

		if (isEventStream) {
			return new Response(response.body, {
				status: response.status,
				statusText: response.statusText,
				headers: responseHeaders
			});
		}

		const body = await response.arrayBuffer();
		return new Response(body, {
			status: response.status,
			statusText: response.statusText,
			headers: responseHeaders
		});
	} catch {
		return new Response(JSON.stringify({ detail: 'Backend unavailable' }), {
			status: 502,
			headers: { 'content-type': 'application/json' }
		});
	}
};

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
export const OPTIONS = handler;
