import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { app } from "../backend/app.js";
import { pool, migrate } from "../backend/db.js";
import { randomBytes } from "node:crypto";
import type { Server } from "node:http";
let server: Server;
let base: string;
let cookieA = "";
let cookieB = "";
let project: number;
let task: number;
const suffix = randomBytes(6).toString("hex");
const emails = [`a-${suffix}@example.test`, `b-${suffix}@example.test`];
async function request(
  path: string,
  method = "GET",
  body?: unknown,
  cookie = cookieA,
  csrf = true,
) {
  const r = await fetch(base + path, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(csrf ? { "X-SecureTask": "1" } : {}),
      Cookie: cookie,
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await r.text();
  let data: any;
  try {
    data = JSON.parse(text);
  } catch {
    data = text;
  }
  return {
    status: r.status,
    data,
    cookie: r.headers.get("set-cookie")?.split(";")[0] || "",
  };
}
before(async () => {
  await migrate();
  server = app.listen(0, "127.0.0.1");
  await new Promise<void>((r) => server.once("listening", r));
  base = "http://127.0.0.1:" + (server.address() as any).port;
});
after(async () => {
  await pool.query(
    "DELETE FROM projects WHERE owner_id IN (SELECT id FROM users WHERE email=ANY($1))",
    [emails],
  );
  await pool.query(
    "DELETE FROM audit WHERE user_id IN (SELECT id FROM users WHERE email=ANY($1))",
    [emails],
  );
  await pool.query("DELETE FROM users WHERE email=ANY($1)", [emails]);
  await new Promise<void>((r) => server.close(() => r()));
  await pool.end();
});
test("health and authentication protection", async () => {
  assert.equal((await request("/health/ready")).status, 200);
  assert.equal((await request("/api/projects")).status, 401);
  assert.equal(
    (await request("/api/register", "POST", {}, "", false)).status,
    403,
  );
  assert.equal(
    (
      await request("/api/register", "POST", {
        email: emails[0],
        name: "Alice",
        password: "short",
      })
    ).status,
    400,
  );
});
test("register two users and prevent duplicate account", async () => {
  let r = await request("/api/register", "POST", {
    email: emails[0],
    name: "Alice",
    password: "a-secure-test-password-123",
  });
  assert.equal(r.status, 201);
  assert.equal(r.data.role, "member");
  cookieA = r.cookie;
  assert.ok(cookieA);
  r = await request(
    "/api/register",
    "POST",
    { email: emails[1], name: "Bob", password: "another-test-password-123" },
    "",
  );
  cookieB = r.cookie;
  assert.equal(r.status, 201);
  assert.equal(
    (
      await request("/api/register", "POST", {
        email: emails[0],
        name: "Alice",
        password: "a-secure-test-password-123",
      })
    ).status,
    409,
  );
});
test("create project and task, enforce ownership", async () => {
  let r = await request("/api/projects", "POST", {
    name: "Integration project",
  });
  assert.equal(r.status, 201);
  project = r.data.id;
  r = await request("/api/tasks", "POST", {
    project_id: project,
    title: "Ship securely",
    priority: "high",
  });
  assert.equal(r.status, 201);
  task = r.data.id;
  assert.equal(
    (await request("/api/tasks", "PATCH", { status: "done" })).status,
    404,
  );
  assert.equal(
    (await request("/api/tasks/" + task, "PATCH", { status: "done" }, cookieB))
      .status,
    404,
  );
  assert.equal(
    (
      await request(
        "/api/tasks",
        "POST",
        { project_id: project, title: "Unauthorized" },
        cookieB,
      )
    ).status,
    404,
  );
  assert.equal(
    (await request("/api/tasks", "GET", undefined, cookieB)).data.length,
    0,
  );
});
test("SQL injection input stays data and preserves tasks", async () => {
  const r = await request(
    "/api/tasks?search=" + encodeURIComponent("' OR 1=1; DROP TABLE tasks;--"),
  );
  assert.equal(r.status, 200);
  assert.equal(r.data.length, 0);
  assert.ok((await request("/api/tasks")).data.some((t: any) => t.id === task));
});
test("status, comments, audit and admin authorization", async () => {
  assert.equal(
    (await request("/api/tasks/" + task, "PATCH", { status: "done" })).data
      .status,
    "done",
  );
  assert.equal(
    (await request("/api/tasks/" + task, "PATCH", { status: "unknown" }))
      .status,
    400,
  );
  assert.equal(
    (
      await request("/api/tasks/" + task + "/comments", "POST", {
        body: "Ready for release",
      })
    ).status,
    201,
  );
  assert.equal(
    (await request("/api/tasks/" + task + "/comments")).data.length,
    1,
  );
  assert.equal(
    (
      await request(
        "/api/tasks/" + task + "/comments",
        "POST",
        { body: "Intrusion" },
        cookieB,
      )
    ).status,
    404,
  );
  assert.ok((await request("/api/audit")).data.length >= 2);
  assert.equal((await request("/api/admin/users")).status, 403);
});
test("logout invalidates session; login issues new session", async () => {
  assert.equal((await request("/api/logout", "POST", {})).status, 204);
  assert.equal((await request("/api/me")).status, 401);
  assert.equal(
    (
      await request("/api/login", "POST", {
        email: emails[0],
        password: "wrong-password-long",
      })
    ).status,
    401,
  );
  const r = await request("/api/login", "POST", {
    email: emails[0],
    password: "a-secure-test-password-123",
  });
  assert.equal(r.status, 200);
  cookieA = r.cookie;
  assert.equal((await request("/api/tasks/" + task, "DELETE")).status, 204);
});
