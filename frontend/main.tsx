import "@fontsource/dm-sans/400.css";
import "@fontsource/dm-sans/500.css";
import "@fontsource/dm-sans/600.css";
import "@fontsource/dm-sans/700.css";
import "@fontsource/manrope/400.css";
import "@fontsource/manrope/600.css";
import "@fontsource/manrope/700.css";
import "@fontsource/manrope/800.css";
import React, { useState, useEffect } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";
type Task = {
  id: number;
  title: string;
  status: string;
  priority: string;
  project_name: string;
  due_date: string | null;
};
type Project = { id: number; name: string };
async function api(path: string, method = "GET", body?: unknown) {
  const r = await fetch("/api" + path, {
    method,
    headers: { "Content-Type": "application/json", "X-SecureTask": "1" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) {
    const d = await r.json().catch(() => ({ error: "Request failed" }));
    throw Error(d.error);
  }
  return r.status === 204 ? null : r.json();
}
function App() {
  const [user, setUser] = useState<any>(null),
    [ready, setReady] = useState(false),
    [mode, setMode] = useState("login"),
    [error, setError] = useState(""),
    [projects, setProjects] = useState<Project[]>([]),
    [tasks, setTasks] = useState<Task[]>([]),
    [filter, setFilter] = useState("all"),
    [search, setSearch] = useState(""),
    [view, setView] = useState("board"),
    [audit, setAudit] = useState<any[]>([]),
    [comments, setComments] = useState<any[]>([]),
    [selected, setSelected] = useState<Task | null>(null),
    [admin, setAdmin] = useState<any[]>([]);
  useEffect(() => {
    api("/me")
      .then(setUser)
      .catch(() => {})
      .finally(() => setReady(true));
  }, []);
  async function load() {
    const [p, t] = await Promise.all([api("/projects"), api("/tasks")]);
    setProjects(p);
    setTasks(t);
  }
  useEffect(() => {
    if (user) void load().catch((e) => setError(e.message));
  }, [user]);
  async function action(fn: () => Promise<void>) {
    try {
      setError("");
      await fn();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  if (!ready) return <div className="loading">Loading Secure Task By Akuphe…</div>;
  if (!user)
    return (
      <main className="auth">
        <div className="pitch">
          <div className="brand">◈ Secure Task By Akuphe</div>
          <span className="eyebrow">BUILD. REVIEW. SHIP.</span>
          <h1>
            Good work.
            <br />
            Secure by design.
          </h1>
          <p>
            A focused workspace for your next release. Bring your projects,
            tasks, and team’s momentum together.
          </p>
          <div className="trust">
            ● AWS ECS &nbsp; / &nbsp; Security first &nbsp; / &nbsp; Open source
          </div>
        </div>
        <form
          className="authform"
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            void action(async () =>
              setUser(await api("/" + mode, "POST", Object.fromEntries(f))),
            );
          }}
        >
          <span className="eyebrow">YOUR WORKSPACE AWAITS</span>
          <h2>
            {mode === "login" ? "Welcome back." : "Start something good."}
          </h2>
          {mode === "register" && (
            <label>
              Your name
              <input name="name" required maxLength={80} />
            </label>
          )}
          <label>
            Email address
            <input name="email" type="email" required autoComplete="email" />
          </label>
          <label>
            Password
            <input
              name="password"
              type="password"
              minLength={12}
              maxLength={128}
              required
              autoComplete={
                mode === "login" ? "current-password" : "new-password"
              }
            />
          </label>
          <small>Use at least 12 characters.</small>
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          <button>{mode === "login" ? "Sign in →" : "Create account →"}</button>
          <button
            className="plain"
            type="button"
            onClick={() => {
              setMode(mode === "login" ? "register" : "login");
              setError("");
            }}
          >
            {mode === "login"
              ? "New here? Create an account"
              : "Already registered? Sign in"}
          </button>
        </form>
      </main>
    );
  const visible = tasks.filter(
    (t) =>
      (filter === "all" || String(t.project_name) === filter) &&
      t.title.toLowerCase().includes(search.toLowerCase()),
  );
  return (
    <div className="shell">
      <aside>
        <div className="brand">◈ Secure Task By Akuphe</div>
        <div className="workspace">PERSONAL WORKSPACE</div>
        <button
          className={view === "board" ? "nav active" : "nav"}
          onClick={() => setView("board")}
        >
          ▦ &nbsp; Overview
        </button>
        <button
          className={view === "audit" ? "nav active" : "nav"}
          onClick={() =>
            void action(async () => {
              setAudit(await api("/audit"));
              setView("audit");
            })
          }
        >
          ◷ &nbsp; Activity
        </button>
        {user.role === "admin" && (
          <button
            className="nav"
            onClick={() =>
              void action(async () => {
                setAdmin(await api("/admin/users"));
                setView("admin");
              })
            }
          >
            ♙ &nbsp; Users
          </button>
        )}
        <div className="workspace">PROJECTS</div>
        <button
          className="nav"
          onClick={() => {
            setFilter("all");
            setView("board");
          }}
        >
          All projects <span>{projects.length}</span>
        </button>
        {projects.map((p) => (
          <button
            className="nav"
            key={p.id}
            onClick={() => {
              setFilter(p.name);
              setView("board");
            }}
          >
            ▫ &nbsp;{p.name}
          </button>
        ))}
        <form
          className="projectform"
          onSubmit={(e) => {
            e.preventDefault();
            const form = e.currentTarget;
            const name = new FormData(form).get("name");
            void action(async () => {
              await api("/projects", "POST", { name });
              form.reset();
              await load();
            });
          }}
        >
          <input
            name="name"
            placeholder="New project"
            aria-label="New project name"
            required
            maxLength={100}
          />
          <button aria-label="Create project">+</button>
        </form>
        <div className="profile">
          <div className="avatar">{user.name[0].toUpperCase()}</div>
          <div>
            <b>{user.name}</b>
            <small>{user.role}</small>
          </div>
          <button
            className="plain"
            onClick={() =>
              void action(async () => {
                await api("/logout", "POST");
                setUser(null);
              })
            }
            aria-label="Sign out"
          >
            ↗
          </button>
        </div>
      </aside>
      <main className="content">
        <header>
          <span>
            Workspace{" "}
            <span className="muted">
              / {view === "board" ? "Overview" : view}
            </span>
          </span>
          <span className="live">● All systems ready</span>
        </header>
        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}
        <div className="heading">
          <div>
            <span className="eyebrow">MAKE PROGRESS, EVERY DAY</span>
            <h1>
              {view === "board"
                ? "Your work, in focus."
                : view === "audit"
                  ? "Workspace activity."
                  : "Workspace users."}
            </h1>
            <p className="muted">
              {view === "board"
                ? "Turn plans into progress. One task at a time."
                : "A clear record of your workspace."}
            </p>
          </div>
          <div className="date">
            {new Date().toLocaleDateString(undefined, {
              month: "short",
              day: "numeric",
              year: "numeric",
            })}
          </div>
        </div>
        {view === "board" ? (
          <>
            <div className="metrics">
              {[
                ["Total tasks", tasks.length, "Across your workspace"],
                [
                  "In progress",
                  tasks.filter((t) => t.status === "progress").length,
                  "Keep the momentum going",
                ],
                [
                  "Completed",
                  tasks.filter((t) => t.status === "done").length,
                  "One step closer to shipping",
                ],
              ].map(([name, num, note]) => (
                <div className="metric" key={name}>
                  <span>{name}</span>
                  <strong>{num}</strong>
                  <small>{note}</small>
                </div>
              ))}
            </div>
            <section className="newtask">
              <h3>Create a task</h3>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const form = e.currentTarget,
                    f = new FormData(form);
                  void action(async () => {
                    await api("/tasks", "POST", {
                      title: f.get("title"),
                      project_id: Number(f.get("project")),
                      priority: f.get("priority"),
                      due_date: f.get("due") || null,
                    });
                    form.reset();
                    await load();
                  });
                }}
              >
                <input
                  name="title"
                  placeholder="What needs to get done?"
                  required
                  maxLength={200}
                  aria-label="Task title"
                />
                <select name="project" required aria-label="Project">
                  <option value="">Select project</option>
                  {projects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
                <select name="priority" aria-label="Priority">
                  <option value="medium">Medium priority</option>
                  <option value="high">High priority</option>
                  <option value="low">Low priority</option>
                </select>
                <input type="date" name="due" aria-label="Due date" />
                <button disabled={!projects.length}>+ Add task</button>
              </form>
              {!projects.length && (
                <small>
                  Create your first project in the sidebar to get started.
                </small>
              )}
            </section>
            <div className="boardtitle">
              <h2>{filter === "all" ? "Task board" : filter}</h2>
              <input
                placeholder="Search tasks…"
                aria-label="Search tasks"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <div className="board">
              {[
                ["todo", "To do"],
                ["progress", "In progress"],
                ["done", "Completed"],
              ].map(([status, label]) => (
                <section className="column" key={status}>
                  <h3>
                    <i className={status} />
                    {label}
                    <span>
                      {visible.filter((t) => t.status === status).length}
                    </span>
                  </h3>
                  {visible
                    .filter((t) => t.status === status)
                    .map((t) => (
                      <article className="task" key={t.id}>
                        <div className="tasktop">
                          <span className={"priority " + t.priority}>
                            {t.priority}
                          </span>
                          <button
                            className="plain"
                            aria-label={"Delete " + t.title}
                            onClick={() =>
                              void action(async () => {
                                await api("/tasks/" + t.id, "DELETE");
                                await load();
                              })
                            }
                          >
                            ×
                          </button>
                        </div>
                        <h4>{t.title}</h4>
                        <small>{t.project_name}</small>
                        {t.due_date && (
                          <small>Due {t.due_date.slice(0, 10)}</small>
                        )}
                        <div className="taskbottom">
                          <select
                            aria-label={"Status of " + t.title}
                            value={t.status}
                            onChange={(e) =>
                              void action(async () => {
                                await api("/tasks/" + t.id, "PATCH", {
                                  status: e.target.value,
                                });
                                await load();
                              })
                            }
                          >
                            {["todo", "progress", "done"].map((s) => (
                              <option key={s}>{s}</option>
                            ))}
                          </select>
                          <button
                            className="plain"
                            onClick={() =>
                              void action(async () => {
                                setComments(
                                  await api("/tasks/" + t.id + "/comments"),
                                );
                                setSelected(t);
                              })
                            }
                          >
                            Comments ↗
                          </button>
                        </div>
                      </article>
                    ))}
                  {!visible.some((t) => t.status === status) && (
                    <div className="empty">
                      A little room for your next idea.
                    </div>
                  )}
                </section>
              ))}
            </div>
          </>
        ) : view === "audit" ? (
          <div className="list">
            {audit.map((a, i) => (
              <div key={i}>
                <b>{a.action}</b>
                <time>{new Date(a.created_at).toLocaleString()}</time>
              </div>
            ))}
            {!audit.length && <p>No activity yet.</p>}
          </div>
        ) : (
          <div className="list">
            {admin.map((a) => (
              <div key={a.id}>
                <b>{a.name}</b>
                <span>
                  {a.email} · {a.role}
                </span>
              </div>
            ))}
          </div>
        )}
        <footer>
          SECURETASK <span>Built to move forward.</span>
        </footer>
      </main>
      {selected && (
        <div className="overlay">
          <section className="modal">
            <button className="plain close" onClick={() => setSelected(null)}>
              Close ×
            </button>
            <h2>{selected.title}</h2>
            <h3>Conversation</h3>
            {comments.map((c) => (
              <div className="comment" key={c.id}>
                <b>{c.name}</b>
                <p>{c.body}</p>
              </div>
            ))}
            {!comments.length && (
              <p className="muted">Start the conversation.</p>
            )}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const form = e.currentTarget,
                  body = new FormData(form).get("body");
                void action(async () => {
                  await api("/tasks/" + selected.id + "/comments", "POST", {
                    body,
                  });
                  setComments(await api("/tasks/" + selected.id + "/comments"));
                  form.reset();
                });
              }}
            >
              <textarea
                name="body"
                required
                maxLength={2000}
                aria-label="Comment"
              />
              <button>Add comment</button>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
