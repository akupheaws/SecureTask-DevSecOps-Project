import argparse, json, secrets, urllib.request, http.cookiejar


def smoke(url):
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )

    def request(path, method="GET", data=None):
        req = urllib.request.Request(
            url.rstrip("/") + path,
            method=method,
            data=json.dumps(data).encode() if data is not None else None,
            headers={"Content-Type": "application/json", "X-SecureTask": "1"},
        )
        with opener.open(req, timeout=30) as response:
            return json.load(response) if response.status != 204 else None

    assert request("/health/ready")["status"] == "ready"
    user = request(
        "/api/register",
        "POST",
        {
            "name": "Release smoke test",
            "email": "smoke-" + secrets.token_hex(6) + "@example.test",
            "password": secrets.token_urlsafe(24),
        },
    )
    p = request("/api/projects", "POST", {"name": "Release verification"})
    t = request(
        "/api/tasks",
        "POST",
        {"project_id": p["id"], "title": "Verify deployed image", "priority": "high"},
    )
    assert (
        request("/api/tasks/" + str(t["id"]), "PATCH", {"status": "done"})["status"]
        == "done"
    )
    request(
        "/api/tasks/" + str(t["id"]) + "/comments",
        "POST",
        {"body": "Smoke test passed"},
    )
    assert len(request("/api/tasks/" + str(t["id"]) + "/comments")) == 1
    request("/api/tasks/" + str(t["id"]), "DELETE")
    request("/api/logout", "POST", {})
    print("Smoke passed: registration, session, projects, tasks, comments, logout")


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("url")
    args = a.parse_args()
    smoke(args.url)
