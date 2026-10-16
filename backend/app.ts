import express from "express";
import helmet from "helmet";
import { rateLimit } from "express-rate-limit";
import bcrypt from "bcryptjs";
import { randomBytes, createHash } from "node:crypto";
import { z } from "zod";
import { pool } from "./db.js";
const hash = (s: string) => createHash("sha256").update(s).digest("hex");
export const app = express();
app.disable("x-powered-by");
app.set("trust proxy", 1);
app.use(
  helmet({
    contentSecurityPolicy: {
      directives: {
        "upgrade-insecure-requests":
          process.env.ALLOW_HTTP_DEMO === "true" ? null : [],
      },
    },
  }),
);
app.use(express.json({ limit: "32kb" }));
app.get("/health/live", (_req, res) => res.json({ status: "ok" }));
app.get("/health/ready", async (_req, res) => {
  await pool.query("SELECT 1");
  res.json({ status: "ready" });
});
app.use("/api", rateLimit({ windowMs: 60_000, limit: 120 }));
app.use("/api", (req, res, next) => {
  if (
    !["GET", "HEAD", "OPTIONS"].includes(req.method) &&
    req.get("X-SecureTask") !== "1"
  ) {
    res.status(403).json({ error: "Required request header missing" });
    return;
  }
  next();
});
const credentials = z.object({
  email: z.email().max(254),
  password: z.string().min(12).max(128),
  name: z.string().trim().min(1).max(80),
});
async function issueSession(id: number, res: express.Response) {
  const token = randomBytes(32).toString("hex");
  await pool.query(
    "INSERT INTO sessions(token_hash,user_id,expires_at) VALUES($1,$2,now()+interval '8 hours')",
    [hash(token), id],
  );
  res.cookie("session", token, {
    httpOnly: true,
    secure:
      process.env.NODE_ENV === "production" &&
      process.env.ALLOW_HTTP_DEMO !== "true",
    sameSite: "strict",
    maxAge: 8 * 3600_000,
    path: "/",
  });
}
app.post(
  "/api/register",
  rateLimit({ windowMs: 15 * 60_000, limit: 10 }),
  async (req, res) => {
    const data = credentials.parse(req.body);
    const password = await bcrypt.hash(data.password, 12);
    const result = await pool.query(
      "INSERT INTO users(email,name,password) VALUES($1,$2,$3) RETURNING id,email,name,role",
      [data.email.toLowerCase(), data.name, password],
    );
    await issueSession(result.rows[0].id, res);
    await pool.query("INSERT INTO audit(user_id,action) VALUES($1,$2)", [
      result.rows[0].id,
      "Account registered",
    ]);
    res.status(201).json(result.rows[0]);
  },
);
app.post(
  "/api/login",
  rateLimit({ windowMs: 15 * 60_000, limit: 15 }),
  async (req, res) => {
    const data = credentials.omit({ name: true }).parse(req.body);
    const result = await pool.query("SELECT * FROM users WHERE email=$1", [
      data.email.toLowerCase(),
    ]);
    const user = result.rows[0];
    if (!user || !(await bcrypt.compare(data.password, user.password))) {
      res.status(401).json({ error: "Invalid credentials" });
      return;
    }
    await issueSession(user.id, res);
    res.json({
      id: user.id,
      email: user.email,
      name: user.name,
      role: user.role,
    });
  },
);
app.use("/api", async (req, res, next) => {
  const token = req.headers.cookie
    ?.split(";")
    .map((x) => x.trim())
    .find((x) => x.startsWith("session="))
    ?.slice(8);
  if (!token) {
    res.status(401).json({ error: "Sign in to continue" });
    return;
  }
  const result = await pool.query(
    "SELECT u.id,u.email,u.name,u.role FROM sessions s JOIN users u ON s.user_id=u.id WHERE s.token_hash=$1 AND s.expires_at>now()",
    [hash(token)],
  );
  if (!result.rows[0]) {
    res.status(401).json({ error: "Session expired" });
    return;
  }
  res.locals.user = result.rows[0];
  res.locals.token = token;
  next();
});
app.get("/api/me", (_req, res) => res.json(res.locals.user));
app.post("/api/logout", async (_req, res) => {
  await pool.query("DELETE FROM sessions WHERE token_hash=$1", [
    hash(res.locals.token),
  ]);
  res.clearCookie("session", { path: "/" });
  res.sendStatus(204);
});
app.get("/api/projects", async (_req, res) =>
  res.json(
    (
      await pool.query("SELECT * FROM projects WHERE owner_id=$1 ORDER BY id", [
        res.locals.user.id,
      ])
    ).rows,
  ),
);
app.post("/api/projects", async (req, res) => {
  const { name } = z
    .object({ name: z.string().trim().min(1).max(100) })
    .parse(req.body);
  res
    .status(201)
    .json(
      (
        await pool.query(
          "INSERT INTO projects(owner_id,name) VALUES($1,$2) RETURNING *",
          [res.locals.user.id, name],
        )
      ).rows[0],
    );
});
app.get("/api/tasks", async (req, res) => {
  const search = z
    .string()
    .max(100)
    .parse(req.query.search || "");
  res.json(
    (
      await pool.query(
        "SELECT t.*,p.name AS project_name FROM tasks t JOIN projects p ON t.project_id=p.id WHERE p.owner_id=$1 AND t.title ILIKE $2 ORDER BY t.id DESC",
        [res.locals.user.id, `%${search}%`],
      )
    ).rows,
  );
});
const task = z.object({
  project_id: z.number().int().positive(),
  title: z.string().trim().min(1).max(200),
  priority: z.enum(["low", "medium", "high"]).default("medium"),
  due_date: z
    .string()
    .regex(/^\d{4}-\d{2}-\d{2}$/)
    .nullable()
    .optional(),
});
app.post("/api/tasks", async (req, res) => {
  const t = task.parse(req.body);
  const result = await pool.query(
    "INSERT INTO tasks(project_id,title,priority,due_date) SELECT id,$2,$3,$4 FROM projects WHERE id=$1 AND owner_id=$5 RETURNING *",
    [t.project_id, t.title, t.priority, t.due_date || null, res.locals.user.id],
  );
  if (!result.rowCount) {
    res.status(404).json({ error: "Project not found" });
    return;
  }
  await pool.query("INSERT INTO audit(user_id,action) VALUES($1,$2)", [
    res.locals.user.id,
    `Created task ${result.rows[0].id}`,
  ]);
  res.status(201).json(result.rows[0]);
});
app.patch("/api/tasks/:id", async (req, res) => {
  const { status } = z
    .object({ status: z.enum(["todo", "progress", "done"]) })
    .parse(req.body);
  const result = await pool.query(
    "UPDATE tasks t SET status=$1 FROM projects p WHERE t.id=$2 AND t.project_id=p.id AND p.owner_id=$3 RETURNING t.*",
    [status, req.params.id, res.locals.user.id],
  );
  if (!result.rowCount) {
    res.status(404).json({ error: "Task not found" });
    return;
  }
  res.json(result.rows[0]);
});
app.delete("/api/tasks/:id", async (req, res) => {
  const result = await pool.query(
    "DELETE FROM tasks t USING projects p WHERE t.id=$1 AND t.project_id=p.id AND p.owner_id=$2",
    [req.params.id, res.locals.user.id],
  );
  res.sendStatus(result.rowCount ? 204 : 404);
});
app.get("/api/tasks/:id/comments", async (req, res) => {
  res.json(
    (
      await pool.query(
        "SELECT c.id,c.body,c.created_at,u.name FROM comments c JOIN users u ON u.id=c.user_id JOIN tasks t ON t.id=c.task_id JOIN projects p ON p.id=t.project_id WHERE t.id=$1 AND p.owner_id=$2 ORDER BY c.id",
        [req.params.id, res.locals.user.id],
      )
    ).rows,
  );
});
app.post("/api/tasks/:id/comments", async (req, res) => {
  const { body } = z
    .object({ body: z.string().trim().min(1).max(2000) })
    .parse(req.body);
  const result = await pool.query(
    "INSERT INTO comments(task_id,user_id,body) SELECT t.id,$2,$3 FROM tasks t JOIN projects p ON p.id=t.project_id WHERE t.id=$1 AND p.owner_id=$2 RETURNING *",
    [req.params.id, res.locals.user.id, body],
  );
  if (!result.rowCount) {
    res.sendStatus(404);
    return;
  }
  res.status(201).json(result.rows[0]);
});
app.get("/api/audit", async (_req, res) =>
  res.json(
    (
      await pool.query(
        "SELECT action,created_at FROM audit WHERE user_id=$1 ORDER BY id DESC LIMIT 50",
        [res.locals.user.id],
      )
    ).rows,
  ),
);
app.get("/api/admin/users", async (_req, res) => {
  if (res.locals.user.role !== "admin") {
    res.sendStatus(403);
    return;
  }
  res.json(
    (await pool.query("SELECT id,email,name,role FROM users ORDER BY id")).rows,
  );
});
app.use(express.static("dist/public"));
app.get("/{*path}", (_req, res) =>
  res.sendFile("index.html", { root: "dist/public" }),
);
app.use(
  (
    err: any,
    _req: express.Request,
    res: express.Response,
    _next: express.NextFunction,
  ) => {
    if (err instanceof z.ZodError) {
      res.status(400).json({
        error: "Invalid input",
        details: err.issues.map((i) => i.message),
      });
      return;
    }
    if (err.code === "23505") {
      res.status(409).json({ error: "Account already exists" });
      return;
    }
    console.error({ event: "request_failed", code: err.code || "internal" });
    res.status(500).json({ error: "Internal server error" });
  },
);
