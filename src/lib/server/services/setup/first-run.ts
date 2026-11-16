import type { Database } from "#lib/server/db/client.ts";
import { ownerExists } from "#lib/server/db/owner.ts";
import {
	type BootstrapToken,
	formatToken,
	issueToken,
	TOKEN_LIFETIME_MS,
} from "#lib/server/security/bootstrap-token.ts";

export type FirstRunOptions = {
	readonly db: Database;
	/** `ORIGIN`, parsed, so the printed line can give the full address. */
	readonly origin: string | undefined;
	/** Where the token line goes: standard output, never the logs. */
	readonly print?: (line: string) => void;
	readonly lifetimeMs?: number;
};

/** First run's state, in memory (one process, D17): startup loads it, the claim updates it. */
let claimed = false;
let token: BootstrapToken | undefined;
let timer: ReturnType<typeof setTimeout> | undefined;
let settings: Required<Omit<FirstRunOptions, "db">> | undefined;

/** Console output for whoever runs the server; it still reaches the container's output. */
const toStandardOutput = (line: string) => process.stdout.write(`${line}\n`);

/**
 * Loads first run's state at startup. While no owner exists, a bootstrap token is printed with
 * the address to claim the instance at, and a new one every time it expires; once the instance
 * is claimed, none is printed again (SPEC-setup.md, "The bootstrap token").
 */
export async function startFirstRun(options: FirstRunOptions): Promise<void> {
	stopFirstRun();
	settings = {
		origin: options.origin,
		print: options.print ?? toStandardOutput,
		lifetimeMs: options.lifetimeMs ?? TOKEN_LIFETIME_MS,
	};
	claimed = await ownerExists(options.db);
	token = undefined;
	if (!claimed) renewToken();
}

/** Stops the token's timer, as shutdown does on its signal. */
export function stopFirstRun(): void {
	clearTimeout(timer);
	timer = undefined;
}

/** Whether the instance has been claimed. */
export function isClaimed(): boolean {
	return claimed;
}

/** Issues and prints a new token, and schedules the next; never once the instance is claimed. */
function renewToken(): void {
	if (settings === undefined || claimed) return;
	clearTimeout(timer);
	token = issueToken(Date.now(), settings.lifetimeMs);
	const address = `${settings.origin ?? ""}/setup`;
	const minutes = Math.round(settings.lifetimeMs / 60_000);
	settings.print(
		`Setup token: ${formatToken(token.value)} (valid for ${minutes} minutes). Open ${address} to claim this Zondarr.`,
	);
	timer = setTimeout(renewToken, settings.lifetimeMs);
	timer.unref?.();
}
