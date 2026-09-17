import { execFileSync, spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const require = createRequire(resolve("frontend/package.json"));
const ts =
	require("typescript") as typeof import("../../frontend/node_modules/typescript");
const temporary = mkdtempSync(join(tmpdir(), "zondarr-api-ci-"));
const generated = "frontend/src/lib/api/.ci-types.d.ts";
const env = {
	...process.env,
	SECRET_KEY: "ci-schema-only-ephemeral-secret-at-least-32",
	DATABASE_URL: "sqlite+aiosqlite:///:memory:",
};
try {
	const schema = execFileSync(
		"backend/.venv/bin/python",
		[
			"-c",
			"import sys, msgspec; from zondarr.app import app; sys.stdout.buffer.write(msgspec.json.encode(app.openapi_schema.to_schema()))",
		],
		{ env },
	);
	const schemaFile = join(temporary, "openapi.json");
	await Bun.write(schemaFile, schema);
	execFileSync(
		"frontend/node_modules/.bin/openapi-typescript",
		[schemaFile, "-o", generated],
		{ stdio: "inherit" },
	);
	execFileSync(
		"frontend/node_modules/.bin/biome",
		["format", "--write", generated],
		{ stdio: "inherit" },
	);
	const printer = ts.createPrinter({ removeComments: true });
	const normalize = (path: string) =>
		printer.printFile(
			ts.createSourceFile(
				path,
				readFileSync(path, "utf8"),
				ts.ScriptTarget.Latest,
				true,
				ts.ScriptKind.TS,
			),
		);
	// Litestar's generated example timestamps vary with the date. They are JSDoc,
	// not API types. Compare the parsed declarations without those comments.
	const expected = normalize("frontend/src/lib/api/types.d.ts");
	const actual = normalize(generated);
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
		console.error(`Normalized API diagnostics retained in ${diagnostics}`);
		throw new Error(
			"API declarations have drifted. Regenerate frontend API types from the backend schema.",
		);
	}
	console.log("Generated API declarations match the backend schema.");
} finally {
	rmSync(generated, { force: true });
	rmSync(temporary, { recursive: true, force: true });
}
