import { constants } from "node:fs";
import { access, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { ConfigError } from "./config-error.ts";
import { errorCode } from "./error-code.ts";

export type DatabasePathEnv = { readonly ZONDARR_DATABASE_PATH?: string | undefined };

const VARIABLE = "ZONDARR_DATABASE_PATH";
const DEFAULT = "data/zondarr.db";

/**
 * How a message names the database's path: the variable, or the default when the variable is
 * unset, so a message never blames a variable the owner didn't set.
 */
export function databasePathSubject(env: DatabasePathEnv): string {
	return env.ZONDARR_DATABASE_PATH ? VARIABLE : `${VARIABLE} is unset, and the default ${DEFAULT}`;
}

/**
 * Returns the database file's absolute path, resolved against `cwd`. An empty variable counts as
 * unset. The file's folder is created if it is missing, and must be writable.
 */
export async function readDatabasePath(env: DatabasePathEnv, cwd = process.cwd()): Promise<string> {
	const path = resolve(cwd, env.ZONDARR_DATABASE_PATH || DEFAULT);
	const subject = databasePathSubject(env);
	const folder = dirname(path);
	try {
		await mkdir(folder, { recursive: true });
	} catch (error) {
		throw new ConfigError(
			VARIABLE,
			`${subject} names a folder that can't be created (${errorCode(error)})`,
		);
	}
	try {
		await access(folder, constants.W_OK);
	} catch (error) {
		throw new ConfigError(
			VARIABLE,
			`${subject} names a folder that can't be written (${errorCode(error)})`,
		);
	}
	return path;
}
