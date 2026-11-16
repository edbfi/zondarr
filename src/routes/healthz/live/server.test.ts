import { describe, expect, it } from "vitest";
import { GET } from "./+server.ts";

describe("GET /healthz/live", () => {
	// Before startup has opened any database: liveness never touches it.
	it("answers alive, never cached", async () => {
		const response = await GET({} as Parameters<typeof GET>[0]);
		expect(response.status).toBe(200);
		expect(response.headers.get("cache-control")).toBe("no-store");
		expect(await response.json()).toEqual({ status: "alive" });
	});
});
