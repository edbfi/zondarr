import { createLogger } from "./logger.ts";

/** What SvelteKit's server `handleError` hook passes on about a caught error. */
export type CaughtError = {
	/** SvelteKit's category: `app`, `framework` and `validation` errors are expected. */
	readonly kind: string;
	readonly error: unknown;
	readonly method: string;
	/** The request's path, without its query. */
	readonly path: string;
};

const log = createLogger("request");

/**
 * Writes an unexpected error (`kind` `unknown`, thrown by a load, a form action, an endpoint or a
 * hook) as one redacted error entry, in place of SvelteKit's default `console.error`, which is
 * neither redacted nor a JSON line. Expected errors and 404s write nothing. It returns nothing, so
 * the browser keeps SvelteKit's generic message, never the error's text (SPEC-setup.md,
 * "Logging").
 */
export function logUnexpectedError({ kind, error, method, path }: CaughtError): void {
	if (kind !== "unknown") return;
	log.error("unexpected error", { method, path, error });
}
