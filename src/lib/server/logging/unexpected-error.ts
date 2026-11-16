import type { CaughtError } from "@sveltejs/kit/hooks";
import { createLogger } from "./logger.ts";

/** What SvelteKit's server `handleError` hook passes on about a caught error. */
export type UnexpectedErrorInput = {
	/** SvelteKit's category: `app`, `framework` and `validation` errors are expected. */
	readonly kind: CaughtError["kind"];
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
 * "Logging"). It never throws: SvelteKit would print the raw error if it did.
 */
export function logUnexpectedError({ kind, error, method, path }: UnexpectedErrorInput): void {
	if (kind !== "unknown") return;
	try {
		log.error("unexpected error", { method, path, error });
	} catch {
		// The redactor couldn't read this error, so nothing from it is written.
		try {
			log.error("unexpected error", { method, path, error: "[unloggable]" });
		} catch {
			// Standard output itself failed; there is nowhere left to write.
		}
	}
}
