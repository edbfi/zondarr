import { connect } from "@tursodatabase/database";
import { sql } from "drizzle-orm";
import { drizzle } from "drizzle-orm/tursodatabase/database";

/** Opens the database file at `path` (D6: the one connection the app uses). */
export async function openDatabase(path: string) {
	const client = await connect(path);
	return drizzle({ client });
}

export type Database = Awaited<ReturnType<typeof openDatabase>>;

/** A transaction's handle: every statement in a transaction goes through it (D6). */
export type Transaction = Parameters<Parameters<Database["transaction"]>[0]>[0];

/** What a named operation runs on: the database, or a transaction a service opened. */
export type Executor = Database | Transaction;

/** Runs one trivial query, so a health check knows the connection still answers. */
export async function pingDatabase(db: Database): Promise<void> {
	await db.run(sql`select 1`);
}
