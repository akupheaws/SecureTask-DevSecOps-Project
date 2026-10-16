import { pool } from "../backend/db.js";
const email = process.argv[2];
if (!email)
  throw Error("Usage: npx tsx scripts/promote-admin.ts email@example.com");
const result = await pool.query(
  "UPDATE users SET role='admin' WHERE email=$1 RETURNING id",
  [email.toLowerCase()],
);
console.log(
  result.rowCount ? "Administrator role assigned" : "Account not found",
);
await pool.end();
