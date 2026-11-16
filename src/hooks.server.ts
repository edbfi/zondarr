import {
	type Handle,
	type HandleServerError,
	type ServerInit,
	sequence,
} from "@sveltejs/kit/hooks";
import { paraglideMiddleware } from "#lib/paraglide/server.js";
import { logUnexpectedError } from "#lib/server/logging/unexpected-error.ts";
import { securityHeaders, withSecurityHeaders } from "#lib/server/security/headers.ts";
import { currentOrigin, startUp } from "#lib/server/services/setup/startup.ts";
import { building, dev } from "$app/env";
import * as env from "$app/env/private";

export const init: ServerInit = async () => {
	if (!building) await startUp(env, { dev });
};

/** Each request's language (SPEC-i18n.md); it refuses nothing. */
const language: Handle = ({ event, resolve }) =>
	paraglideMiddleware(event.request, ({ request, locale }) =>
		resolve(
			{ ...event, request },
			{ transformPageChunk: ({ html }) => html.replace("%lang%", locale) },
		),
	);

/** The security headers on every response from here on, an early return from a later stage too. */
const headers: Handle = async ({ event, resolve }) =>
	withSecurityHeaders(await resolve(event), securityHeaders(event.request, currentOrigin()));

export const handle = sequence(language, headers);

/**
 * An unexpected error is one redacted log entry, never SvelteKit's default `console.error`; the
 * browser keeps SvelteKit's generic message (SPEC-setup.md, "Logging").
 */
export const handleError: HandleServerError = ({ kind, error, event }) =>
	logUnexpectedError({ kind, error, method: event.request.method, path: event.url.pathname });
