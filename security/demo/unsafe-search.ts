// SCAN-ONLY EXERCISE. Excluded from the application and Docker image.
export async function unsafeSearch(db: any, search: string) {
  return db.query(
    `SELECT * FROM tasks WHERE title LIKE '%${search}%'`
  );
}