export async function unsafeSearch(db: any, search: string) {
  return db.query(
    "SELECT * FROM tasks WHERE title LIKE $1",
    [`%${search}%`]
  );
}
