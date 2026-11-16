import { describe, expect, it } from "vitest";
import { crossOriginAllowed } from "./cross-origin.ts";

type Case = {
	method?: string;
	headers?: Record<string, string | string[] | undefined>;
	isSubRequest?: boolean;
	origin?: string;
};

/** Whether a request with these parts passes, with `ORIGIN` as `origin`. */
function allowed({ method = "POST", headers = {}, isSubRequest = false, origin }: Case): boolean {
	const list = new Headers();
	for (const [name, value] of Object.entries(headers)) {
		if (value === undefined) continue;
		for (const one of Array.isArray(value) ? value : [value]) list.append(name, one);
	}
	return crossOriginAllowed({ method, headers: list, isSubRequest }, origin);
}

const crossSite = {
	origin: "https://evil.example",
	"sec-fetch-site": "cross-site",
	host: "zondarr.example",
};
const sameOrigin = {
	origin: "https://zondarr.example",
	"sec-fetch-site": "same-origin",
	host: "zondarr.example",
};

describe("crossOriginAllowed", () => {
	it.each(["GET", "HEAD", "OPTIONS"])("lets %s through, even from another site", (method) => {
		expect(allowed({ method, headers: crossSite })).toBe(true);
	});

	it.each(["POST", "PUT", "PATCH", "DELETE"])("checks %s", (method) => {
		expect(allowed({ method, headers: crossSite })).toBe(false);
		expect(allowed({ method, headers: sameOrigin })).toBe(true);
	});

	it.each([
		"application/x-www-form-urlencoded",
		"multipart/form-data; boundary=x",
		"text/plain",
		"application/json",
		"",
	])("checks every content type alike: %j", (type) => {
		const contentType = type === "" ? {} : { "content-type": type };
		expect(allowed({ headers: { ...crossSite, ...contentType } })).toBe(false);
		expect(allowed({ headers: { ...sameOrigin, ...contentType } })).toBe(true);
	});

	it("lets an internal subrequest through", () => {
		expect(allowed({ headers: crossSite, isSubRequest: true })).toBe(true);
	});

	describe("a present Origin must be one bare http or https origin, on every branch", () => {
		const malformed: (string | string[])[] = [
			"null",
			"not a url",
			["https://zondarr.example", "https://zondarr.example"],
			"https://zondarr.example/path",
			"https://zondarr.example/",
			"https://u:p@zondarr.example",
			"ftp://zondarr.example",
			// The URL parser repairs these, so the raw text decides.
			"https:zondarr.example",
			"https://zondarr.example\\x",
			"https://zondarr.example:",
		];

		it.each(malformed)("refuses Origin %j even with Sec-Fetch-Site same-origin", (value) => {
			const headers = { origin: value, "sec-fetch-site": "same-origin", host: "zondarr.example" };
			expect(allowed({ headers })).toBe(false);
			expect(allowed({ headers, origin: "https://zondarr.example" })).toBe(false);
		});

		it.each(malformed)("refuses Origin %j against a matching Host", (value) => {
			expect(allowed({ headers: { origin: value, host: "zondarr.example" } })).toBe(false);
		});
	});

	describe("with ORIGIN set", () => {
		const origin = "https://zondarr.example";

		it("lets a present Origin through only when it equals ORIGIN", () => {
			expect(allowed({ origin, headers: { origin: "https://zondarr.example" } })).toBe(true);
			expect(allowed({ origin, headers: { origin: "http://zondarr.example" } })).toBe(false);
			expect(
				allowed({
					origin,
					headers: { origin: "https://evil.example", "sec-fetch-site": "same-origin" },
				}),
			).toBe(false);
		});

		it("compares parsed origins, so case and a default port don't matter", () => {
			expect(allowed({ origin, headers: { origin: "HTTPS://Zondarr.Example" } })).toBe(true);
			expect(allowed({ origin, headers: { origin: "https://zondarr.example:443" } })).toBe(true);
		});

		it.each([
			["same-origin", true],
			["none", true],
			["same-site", false],
			["cross-site", false],
		])("without Origin, needs Sec-Fetch-Site same-origin or none: %s", (site, expected) => {
			expect(allowed({ origin, headers: { "sec-fetch-site": site } })).toBe(expected);
		});
	});

	describe("with ORIGIN unset", () => {
		it.each([
			["same-origin", true],
			["none", true],
			["same-site", false],
			["cross-site", false],
		])(
			"lets a present Sec-Fetch-Site through only as same-origin or none: %s",
			(site, expected) => {
				const headers = { origin: "https://zondarr.example", host: "zondarr.example" };
				expect(allowed({ headers: { ...headers, "sec-fetch-site": site } })).toBe(expected);
			},
		);

		it.each([
			["http://192.168.1.20:3000", "192.168.1.20:3000", true],
			["http://app.test", "app.test:80", true],
			["https://app.test", "app.test:443", true],
			["http://app.test:80", "app.test", true],
			["http://[::1]:3000", "[::1]:3000", true],
			["http://app.test:8080", "app.test", false],
			["http://evil.test:3000", "app.test:3000", false],
			["http://app.test", "", false],
		])("without Sec-Fetch-Site, compares Origin %s with Host %j", (origin, host, expected) => {
			const headers = host === "" ? { origin } : { origin, host };
			expect(allowed({ headers })).toBe(expected);
		});

		it("can't tell http from https by Host alone, the accepted residual risk", () => {
			expect(allowed({ headers: { origin: "https://app.test:3000", host: "app.test:3000" } })).toBe(
				true,
			);
		});
	});

	it("refuses a request with neither Origin nor Sec-Fetch-Site, which zondarr has no route for", () => {
		expect(allowed({ headers: { host: "zondarr.example" } })).toBe(false);
		expect(allowed({ headers: { host: "zondarr.example", cookie: "zondarr_session=x" } })).toBe(
			false,
		);
		expect(allowed({ origin: "https://zondarr.example", headers: {} })).toBe(false);
	});
});
