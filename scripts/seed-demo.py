"""Create a recording workspace. Requires an explicit password and uses normal API flows."""

import os, json, urllib.request, urllib.error, http.cookiejar

base = os.environ.get("APP_URL", "http://127.0.0.1:3000")
password = os.environ["DEMO_PASSWORD"]
email = os.environ.get("DEMO_EMAIL", "video@example.test")
client = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
)


def api(path, data):
    req = urllib.request.Request(
        base + "/api" + path,
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json", "X-SecureTask": "1"},
    )
    with client.open(req) as r:
        return json.load(r)


try:
    api("/register", {"email": email, "name": "Video workspace", "password": password})
except urllib.error.HTTPError as e:
    if e.code != 409:
        raise
    api("/login", {"email": email, "password": password})
for name, items in [
    (
        "Platform engineering",
        [
            ("Provision private network", "done", "medium"),
            ("Build application image", "done", "low"),
            ("Deploy release to ECS", "progress", "high"),
        ],
    ),
    (
        "Security review",
        [
            ("Review source findings", "progress", "high"),
            ("Approve release pipeline", "todo", "medium"),
            ("Run container and runtime scans", "todo", "high"),
        ],
    ),
]:
    project = api("/projects", {"name": name})
    for title, status, priority in items:
        task = api(
            "/tasks",
            {"project_id": project["id"], "title": title, "priority": priority},
        )
        if status != "todo":
            req = urllib.request.Request(
                base + "/api/tasks/" + str(task["id"]),
                method="PATCH",
                data=json.dumps({"status": status}).encode(),
                headers={"Content-Type": "application/json", "X-SecureTask": "1"},
            )
            client.open(req).close()
print("Recording workspace created")
