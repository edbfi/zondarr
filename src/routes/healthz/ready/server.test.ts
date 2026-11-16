import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { closeServices, startUp } from "#lib/server/services/setup/startup.ts";
import { GET } from "./+server.ts";

let root: string;

beforeAll(async () => {
	root = await mkdtemp(join(tmpdir(), "zondarr-ready-"));
	vi.spyOn(process.stdout, "write").mockImplementation((_chunk, ...rest: unknown[]) => {
		const done = rest.find((arg) => typeof arg === "function") as (() => void) | undefined;
		done?.();
		return true;
	});
});

afterAll(async () => {
	await closeServices();
	vi.restoreAllMocks();
	await rm(root, { recursive: true, force: true });
});

// The handler reads nothing from the request event.
const get = () => GET({} as Parameters<typeof GET>[0]);

describe("GET /healthz/ready", () => {
	it("is not ready before the database is open, ready after, and never cached", async () => {
		const before = await get();
		expect(before.status).toBe(503);
		expect(await before.json()).toEqual({ status: "not ready" });

		const key = crypto.getRandomValues(new Uint8Array(32)).toBase64();
		await startUp(
			{ ZONDARR_SECRET_KEY: key, ZONDARR_DATABASE_PATH: join(root, "app.db") },
			{ dev: true },
		);
		const after = await get();
		expect(after.status).toBe(200);
		expect(after.headers.get("cache-control")).toBe("no-store");
		expect(await after.json()).toEqual({ status: "ready" });
	});
});
