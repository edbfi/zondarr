import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';
import { variables } from './env';

// SvelteKit 3 exposes only variables declared in src/env.ts; an undeclared one
// silently reads as undefined. This scan keeps the declarations and the readers in step.
const SRC = join(import.meta.dirname, '.');

function sourceFiles(dir: string): string[] {
	return readdirSync(dir).flatMap((name) => {
		const path = join(dir, name);
		if (statSync(path).isDirectory()) return sourceFiles(path);
		if (!/\.(ts|js|svelte)$/.test(name) || /\.(test|spec)\.ts$/.test(name)) return [];
		return path === join(SRC, 'env.ts') ? [] : [path];
	});
}

function readNames(scope: 'private' | 'public'): Map<string, string[]> {
	const found = new Map<string, string[]>();
	const specifier = `$app/env/${scope}`;
	for (const file of sourceFiles(SRC)) {
		const code = readFileSync(file, 'utf8');
		const names: string[] = [];
		for (const m of code.matchAll(/import\s+\*\s+as\s+(\w+)\s+from\s+['"]([^'"]+)['"]/g)) {
			if (m[2] !== specifier) continue;
			for (const use of code.matchAll(new RegExp(`\\b${m[1]}\\.([A-Za-z_][A-Za-z0-9_]*)`, 'g'))) {
				names.push(use[1] as string);
			}
		}
		for (const m of code.matchAll(/import\s+\{([^}]*)\}\s+from\s+['"]([^'"]+)['"]/g)) {
			if (m[2] !== specifier) continue;
			for (const part of (m[1] as string).split(',')) {
				const name = part.trim().split(/\s+as\s+/)[0];
				if (name) names.push(name);
			}
		}
		for (const name of names) {
			found.set(name, [...(found.get(name) ?? []), relative(SRC, file)]);
		}
	}
	return found;
}

describe('src/env.ts declarations', () => {
	const declared = Object.entries(variables);
	const isPublic = (config: object) => 'public' in config && config.public === true;
	const declaredPrivate = declared.filter(([, c]) => !isPublic(c)).map(([n]) => n);
	const declaredPublic = declared.filter(([, c]) => isPublic(c)).map(([n]) => n);

	it('declares exactly the private variables the code reads', () => {
		expect([...readNames('private').keys()].sort()).toEqual([...declaredPrivate].sort());
	});

	it('declares exactly the public variables the code reads', () => {
		expect([...readNames('public').keys()].sort()).toEqual([...declaredPublic].sort());
	});

	it('reads no environment outside $app/env', () => {
		const offenders = sourceFiles(SRC).filter((file) =>
			/\$env\/|process\.env|Bun\.env|import\.meta\.env\.(?!SSR|DEV|PROD|MODE|BASE_URL)/.test(
				readFileSync(file, 'utf8')
			)
		);
		expect(offenders.map((file) => relative(SRC, file))).toEqual([]);
	});

	it('keeps every variable optional, so unset stays undefined', () => {
		for (const [name, config] of declared) {
			const result = config.schema?.['~standard'].validate(undefined);
			expect(result, name).toEqual({ value: undefined });
			expect(config.schema?.['~standard'].validate(''), name).toEqual({ value: '' });
		}
	});
});
