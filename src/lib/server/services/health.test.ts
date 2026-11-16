import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	databaseReachable,
	healthResponse,
	livenessResponse,
	readinessResponse,
} from "./health.ts";

let lines: string[];

beforeEach(() => {
	lines = [];
	vi.spyOn(process.stdout, "write").mockImplementation((chunk, ...rest: unknown[]) => {
		lines.push(String(chunk));
		const done = rest.find((arg) => typeof arg === "function") as (() => void) | undefined;
		done?.();
		return true;
	});
});

afterEach(() => {
	vi.restoreAllMocks();
});

const reachable = async () => true;
const unreachable = async () => false;

async function expectAnswer(response: Response, status: number, body: unknown) {
	expect(response.status).toBe(status);
	expect(response.headers.get("content-type")).toMatch(/^application\/json\b/);
	expect(response.headers.get("cache-control")).toBe("no-store");
	expect(await response.json()).toEqual(body);
}

describe("the health answers", () => {
	it("reports healthy, or degraded with a 503 when the database check fails", async () => {
		await expectAnswer(await healthResponse(reachable), 200, {
			status: "healthy",
			checks: { database: "ok" },
		});
		await expectAnswer(await healthResponse(unreachable), 503, {
			status: "degraded",
			checks: { database: "failed" },
		});
	});

	it("reports alive without touching the database", async () => {
		await expectAnswer(livenessResponse(), 200, { status: "alive" });
	});

	it("reports ready, or not ready with a 503 when the database check fails", async () => {
		await expectAnswer(await readinessResponse(reachable), 200, { status: "ready" });
		await expectAnswer(await readinessResponse(unreachable), 503, { status: "not ready" });
	});
});

describe("databaseReachable", () => {
	it("is true when the query answers", async () => {
		expect(await databaseReachable(async () => {})).toBe(true);
		expect(lines).toEqual([]);
	});

	it("is false when the query fails, and logs the failure redacted", async () => {
		const failing = async () => {
			throw new Error("SQLITE_IOERR on libsql://u:hunter2@db.local/zondarr?token=abc");
		};
		expect(await databaseReachable(failing)).toBe(false);
		expect(lines).toHaveLength(1);
		expect(JSON.parse(lines[0] ?? "")).toMatchObject({
			level: "error",
			source: "health",
			message: "database check failed",
		});
		expect(lines[0]).not.toContain("hunter2");
		expect(lines[0]).not.toContain("abc");
	});

	it("is false once the query takes longer than its time limit", async () => {
		const started = performance.now();
		expect(await databaseReachable(() => new Promise(() => {}), 50)).toBe(false);
		expect(performance.now() - started).toBeLessThan(1000);
		expect(JSON.parse(lines[0] ?? "")).toMatchObject({ message: "database check failed" });
	});

	it("is false before startup has opened the database", async () => {
		expect(await databaseReachable()).toBe(false);
	});
});
