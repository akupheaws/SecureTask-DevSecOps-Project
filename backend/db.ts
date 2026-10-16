import pg from "pg";
export const pool = new pg.Pool({
  host: process.env.DB_HOST || "127.0.0.1",
  port: Number(process.env.DB_PORT || 5432),
  database: process.env.DB_NAME || "securetask",
  user: process.env.DB_USER || "securetask",
  password: process.env.DB_PASSWORD,
  ssl:
    process.env.DB_SSL === "true"
      ? { rejectUnauthorized: true, ca: process.env.DB_CA }
      : false,
});
export async function migrate() {
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    await client.query("SELECT pg_advisory_xact_lock(743210)");
    await client.query(`
 CREATE TABLE IF NOT EXISTS users(id SERIAL PRIMARY KEY,email TEXT UNIQUE NOT NULL,name TEXT NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'member');
 CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,expires_at TIMESTAMPTZ NOT NULL);
 CREATE TABLE IF NOT EXISTS projects(id SERIAL PRIMARY KEY,owner_id INTEGER REFERENCES users(id),name TEXT NOT NULL,created_at TIMESTAMPTZ DEFAULT now());
 CREATE TABLE IF NOT EXISTS tasks(id SERIAL PRIMARY KEY,project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,title TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'todo',priority TEXT NOT NULL DEFAULT 'medium',due_date DATE,created_at TIMESTAMPTZ DEFAULT now());
 CREATE TABLE IF NOT EXISTS comments(id SERIAL PRIMARY KEY,task_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id),body TEXT NOT NULL,created_at TIMESTAMPTZ DEFAULT now());
 CREATE TABLE IF NOT EXISTS audit(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id),action TEXT NOT NULL,created_at TIMESTAMPTZ DEFAULT now());
 `);
    await client.query("COMMIT");
  } catch (e) {
    await client.query("ROLLBACK");
    throw e;
  } finally {
    client.release();
  }
}
