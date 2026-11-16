import { connect } from "@tursodatabase/database";
import { sql } from "drizzle-orm";
import { drizzle } from "drizzle-orm/tursodatabase/database";

/** Opens the database file at `path` (D6: the one connection the app uses). */
export async function openDatabase(path: string) {
	const client = await connect(path);
	return drizzle({ client });
}

export type Database = Awaited<ReturnType<typeof openDatabase>>;

/** Runs one trivial query, so a health check knows the connection still answers. */
export async function pingDatabase(db: Database): Promise<void> {
	await db.run(sql`select 1`);
}
