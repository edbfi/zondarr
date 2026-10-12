import { execFileSync, spawnSync } from "node:child_process";
import { mkdirSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { generateApiTypes } from "../../frontend/scripts/openapi-types.ts";

const generated = "frontend/src/lib/api/.ci-types.d.ts";
const env = {
	...process.env,
	SECRET_KEY: "ci-schema-only-ephemeral-secret-at-least-32",
	DATABASE_URL: "sqlite+aiosqlite:///:memory:",
};

// Litestar's generated examples are random, and they reach the declarations only as JSDoc.
// Compare the declarations without comments. The generator writes each JSDoc block on lines of
// its own and escapes `*/` inside it, so a block runs from a line starting `/**` to the next
// line ending `*/`; Biome keeps that layout.
function declarations(path: string): string {
	const kept: string[] = [];
	let inComment = false;
	for (const line of readFileSync(path, "utf8").split("\n")) {
		const text = line.trim();
		if (!inComment && text.startsWith("/**")) inComment = true;
		if (!inComment) kept.push(line);
		else if (text.endsWith("*/")) inComment = false;
	}
	if (inComment) throw new Error(`Unterminated comment in ${path}.`);
	return kept.join("\n");
}

try {
	const schema = execFileSync(
		"backend/.venv/bin/python",
		[
			"-c",
			"import sys, msgspec; from zondarr.app import app; sys.stdout.buffer.write(msgspec.json.encode(app.openapi_schema.to_schema()))",
		],
		{ env },
	);
	await Bun.write(generated, generateApiTypes(JSON.parse(schema.toString())));
	execFileSync("node_modules/.bin/biome", ["format", "--write", generated], {
		stdio: "inherit",
	});
	const expected = declarations("frontend/src/lib/api/types.d.ts");
	const actual = declarations(generated);
	if (actual !== expected) {
		const diagnostics = join(
			process.env.RUNNER_TEMP ?? tmpdir(),
			"zondarr-api-diff",
		);
		mkdirSync(diagnostics, { recursive: true });
		const before = join(diagnostics, "committed.d.ts");
		const after = join(diagnostics, "generated.d.ts");
		await Bun.write(before, expected);
		await Bun.write(after, actual);
		const diff = spawnSync("diff", ["-u", before, after], {
			encoding: "utf8",
			maxBuffer: 2_000_000,
		});
		if (diff.status !== 1)
			throw new Error("Could not produce the API declaration diff.");
		await Bun.write(join(diagnostics, "declarations.diff"), diff.stdout);
		console.error(diff.stdout.slice(0, 32_000));
		console.error(`API declaration diagnostics retained in ${diagnostics}`);
		throw new Error(
			"API declarations have drifted. Regenerate frontend API types from the backend schema.",
		);
	}
	console.log("Generated API declarations match the backend schema.");
} finally {
	rmSync(generated, { force: true });
}
