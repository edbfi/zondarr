import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { logUnexpectedError } from "./unexpected-error.ts";

let lines: string[];

beforeEach(() => {
	lines = [];
	vi.spyOn(process.stdout, "write").mockImplementation((chunk) => {
		lines.push(String(chunk));
		return true;
	});
});

afterEach(() => {
	vi.restoreAllMocks();
});

const entries = () => lines.map((line) => JSON.parse(line) as Record<string, unknown>);
const request = { method: "POST", path: "/setup" };

describe("logUnexpectedError", () => {
	it("writes an unexpected error as one redacted error entry, with the request's method and path", () => {
		const cause = new Error("upstream said https://plex.tv/api?X-Plex-Token=cause-token");
		const error = new Error("fetch http://u:hunter2@plex.local/ failed", { cause });
		error.stack = `Error: fetch http://u:hunter2@plex.local/?token=stack-token failed\n    at load`;

		logUnexpectedError({ kind: "unknown", error, ...request });

		expect(lines).toHaveLength(1);
		for (const secret of ["hunter2", "cause-token", "stack-token"]) {
			expect(lines[0]).not.toContain(secret);
		}
		const [entry] = entries();
		expect(entry).toMatchObject({
			level: "error",
			source: "request",
			message: "unexpected error",
			metadata: {
				method: "POST",
				path: "/setup",
				error: { name: "Error", message: "fetch http://[redacted]@plex.local/ failed" },
			},
		});
	});

	it("logs a thrown value that isn't an Error too", () => {
		logUnexpectedError({ kind: "unknown", error: "GET /x?token=abc failed", ...request });
		expect(entries()).toHaveLength(1);
		expect(lines[0]).not.toContain("abc");
	});

	it.each(["app", "framework", "validation"])("writes nothing for a %s error", (kind) => {
		logUnexpectedError({ kind, error: new Error("Not Found"), ...request });
		expect(lines).toEqual([]);
	});

	// The browser keeps SvelteKit's generic message: nothing is returned for the hook to show.
	it("returns nothing, so SvelteKit answers with its generic message", () => {
		expect(
			logUnexpectedError({ kind: "unknown", error: new Error("secret text"), ...request }),
		).toBeUndefined();
	});
});
