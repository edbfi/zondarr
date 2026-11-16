import type { Handle, HandleServerError, ServerInit } from "@sveltejs/kit/hooks";
import { paraglideMiddleware } from "#lib/paraglide/server.js";
import { logUnexpectedError } from "#lib/server/logging/unexpected-error.ts";
import { startUp } from "#lib/server/services/setup/startup.ts";
import { building } from "$app/env";
import * as env from "$app/env/private";

export const init: ServerInit = async () => {
	if (!building) await startUp(env);
};

export const handle: Handle = ({ event, resolve }) =>
	paraglideMiddleware(event.request, ({ request, locale }) =>
		resolve(
			{ ...event, request },
			{ transformPageChunk: ({ html }) => html.replace("%lang%", locale) },
		),
	);

/**
 * An unexpected error is one redacted log entry, never SvelteKit's default `console.error`; the
 * browser keeps SvelteKit's generic message (SPEC-setup.md, "Logging").
 */
export const handleError: HandleServerError = ({ kind, error, event }) =>
	logUnexpectedError({ kind, error, method: event.request.method, path: event.url.pathname });
