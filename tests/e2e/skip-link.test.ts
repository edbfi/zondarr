import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { expect, type Page, test } from "@playwright/test";
import { type Server, startServer } from "./server.ts";

// The claim, zondarr's one-task page, starts with a skip link to its main content, shown only while
// it has focus. Each test runs on a fresh, unclaimed server of its own, where `/setup` is served.

/** Tabs once from the top of the page, then follows the skip link with Enter. */
async function skip(page: Page, name: string) {
	await page.keyboard.press("Tab");
	const link = page.getByRole("link", { name });
	await expect(link).toBeFocused();
	// Shown in full and inside the viewport: `toBeVisible` alone passes for the 1px hidden box.
	const box = await link.evaluate((element) => {
		const { left, top, right, bottom, width } = element.getBoundingClientRect();
		return { left, top, right, bottom, width, viewport: window.innerWidth };
	});
	expect(box.width).toBeGreaterThan(40);
	expect(box.left).toBeGreaterThanOrEqual(0);
	expect(box.top).toBeGreaterThanOrEqual(0);
	expect(box.right).toBeLessThanOrEqual(box.viewport);
	await page.keyboard.press("Enter");
	// Focus lands on the main content, so the next Tab reaches its first field.
	await expect(page.getByRole("main")).toBeFocused();
	await page.keyboard.press("Tab");
	await expect(page.locator("#token")).toBeFocused();
}

let root: string;
let server: Server;

test.beforeEach(async () => {
	root = await mkdtemp(join(tmpdir(), "zondarr-e2e-skip-"));
	server = await startServer(root, { ZONDARR_DATABASE_PATH: join(root, "zondarr.db") });
});

test.afterEach(async () => {
	await server.stop();
	await rm(root, { recursive: true, force: true });
});

test("the first Tab shows the skip link, and following it moves focus into the main content", async ({
	page,
}) => {
	await page.goto(`${server.url}/setup`);
	await page.locator("html[data-hydrated]").waitFor({ state: "attached" });
	const link = page.getByRole("link", { name: "Skip to main content" });
	// Hidden until it has focus: in the page for the keyboard, but taking no room.
	expect(
		await link.evaluate((element) => element.getBoundingClientRect().width),
	).toBeLessThanOrEqual(1);
	await skip(page, "Skip to main content");
});

test.describe("without JavaScript", () => {
	test.use({ javaScriptEnabled: false });

	test("the skip link works the same", async ({ page }) => {
		await page.goto(`${server.url}/setup`);
		await skip(page, "Skip to main content");
	});
});

test.describe("in Danish", () => {
	test.use({ locale: "da-DK" });

	test("the skip link is named in Danish", async ({ page }) => {
		await page.goto(`${server.url}/setup`);
		await page.locator("html[data-hydrated]").waitFor({ state: "attached" });
		await skip(page, "Gå til hovedindholdet");
	});
});
