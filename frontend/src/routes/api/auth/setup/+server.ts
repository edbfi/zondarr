import { readFileSync } from 'node:fs';
import * as env from '$app/env/private';
import * as publicEnv from '$app/env/public';
import { backendRequestHeaders, relayResponseHeaders } from '$lib/server/backend-relay';
import { isSecureRequest } from '$lib/server/request-origin';
import { consumeNonce } from '$lib/server/setup-nonce';
import type { RequestHandler } from './$types';

function readBootstrapToken(): string | null {
	const filePath = env.BOOTSTRAP_TOKEN_FILE;
	if (!filePath) return null;
	try {
		const content = readFileSync(filePath, 'utf-8').trim();
		return content || null;
	} catch {
		return null;
	}
}

export const POST: RequestHandler = async ({ request, cookies, url }) => {
	const internalApiUrl =
		env.INTERNAL_API_URL ?? publicEnv.PUBLIC_API_URL ?? 'http://localhost:8000';
	const upstream = `${internalApiUrl}/api/auth/setup`;

	// As in the /api proxy (M16), plus Content-Length: the body is re-serialized below.
	const headers = backendRequestHeaders(request.headers, ['content-length']);

	let body: string;
	try {
		const parsed = await request.json();
		const hasManualToken = parsed.bootstrap_token && parsed.bootstrap_token !== '';

		if (!hasManualToken) {
			const fileToken = readBootstrapToken();
			if (fileToken) {
				const nonce = cookies.get('zondarr_setup_nonce');
				cookies.delete('zondarr_setup_nonce', { path: '/', secure: isSecureRequest(url) });

				if (!nonce || !consumeNonce(nonce)) {
					return new Response(
						JSON.stringify({
							detail:
								'Setup authorization expired or invalid. Please use the setup URL from server logs.'
						}),
						{
							status: 403,
							headers: { 'content-type': 'application/json' }
						}
					);
				}

				parsed.bootstrap_token = fileToken;
			}
		}

		body = JSON.stringify(parsed);
	} catch {
		body = await request.text();
	}

	headers.set('content-type', 'application/json');

	try {
		const response = await fetch(upstream, {
			method: 'POST',
			headers,
			body,
			redirect: 'manual'
		});

		const responseBody = await response.arrayBuffer();
		return new Response(responseBody, {
			status: response.status,
			statusText: response.statusText,
			// Backend cookies get Secure from this app's own scheme (M16).
			headers: relayResponseHeaders(response.headers, url)
		});
	} catch {
		return new Response(JSON.stringify({ detail: 'Backend unavailable' }), {
			status: 502,
			headers: { 'content-type': 'application/json' }
		});
	}
};
