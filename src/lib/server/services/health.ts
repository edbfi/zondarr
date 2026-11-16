import { pingDatabase } from "#lib/server/db/client.ts";
import { createLogger } from "#lib/server/logging/logger.ts";
import { currentDatabase } from "./setup/startup.ts";

/** How long the database check may take before it counts as failed. */
const CHECK_TIMEOUT_MS = 2000;

const log = createLogger("health");

/**
 * Whether the database answers one trivial query within the time limit. A failure is logged,
 * redacted like every entry, and never reaches the answer (SPEC-setup.md, "Health").
 */
export async function databaseReachable(
	ping: () => Promise<void> = () => pingDatabase(currentDatabase()),
	timeoutMs = CHECK_TIMEOUT_MS,
): Promise<boolean> {
	let timer: ReturnType<typeof setTimeout> | undefined;
	const timeout = new Promise<never>((_, reject) => {
		timer = setTimeout(() => reject(new Error(`no answer within ${timeoutMs} ms`)), timeoutMs);
	});
	try {
		await Promise.race([ping(), timeout]);
		return true;
	} catch (error) {
		log.error("database check failed", { error });
		return false;
	} finally {
		clearTimeout(timer);
	}
}

/** A health answer: public JSON that no cache keeps, never with a version (D24). */
const answer = (status: number, body: unknown) =>
	Response.json(body, { status, headers: { "cache-control": "no-store" } });

/** `/healthz`: overall health, degraded when the database check fails. */
export async function healthResponse(check = databaseReachable): Promise<Response> {
	return (await check())
		? answer(200, { status: "healthy", checks: { database: "ok" } })
		: answer(503, { status: "degraded", checks: { database: "failed" } });
}

/** `/healthz/live`: the process serves requests; it never touches the database. */
export function livenessResponse(): Response {
	return answer(200, { status: "alive" });
}

/** `/healthz/ready`: ready while the database answers. */
export async function readinessResponse(check = databaseReachable): Promise<Response> {
	return (await check()) ? answer(200, { status: "ready" }) : answer(503, { status: "not ready" });
}
