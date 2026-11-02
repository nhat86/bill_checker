"""API contract tests: what the endpoints promise, not how they're built."""

import io


def test_health_ok(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_register_returns_token(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "bob@example.com", "password": "motdepasse123"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["access_token"]
    assert body["user"]["email"] == "bob@example.com"
    assert "password" not in body["user"]  # hash must never leak


def test_register_duplicate_email_409(client, auth_headers):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "alice@example.com", "password": "autremotdepasse"},
    )
    assert resp.status_code == 409


def test_login_wrong_password_401(client, auth_headers):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "wrong-password"},
    )
    assert resp.status_code == 401


def test_me_requires_auth(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_with_token(client, auth_headers):
    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "alice@example.com"


def test_create_session(client, auth_headers):
    resp = client.post("/api/v1/sessions", headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()["status"] == "DRAFT"


def test_session_detail_isolated_per_user(client, auth_headers):
    # user A creates a session
    sid = client.post("/api/v1/sessions", headers=auth_headers).json()["id"]
    # user B registers and tries to read it
    resp2 = client.post(
        "/api/v1/auth/register",
        json={"email": "mallory@example.com", "password": "motdepasse123"},
    )
    headers_b = {"Authorization": f"Bearer {resp2.json()['access_token']}"}
    assert client.get(f"/api/v1/sessions/{sid}", headers=headers_b).status_code == 404


def _png_upload(content: bytes = b"\x89PNG-fake"):
    return ("file", ("photo.png", io.BytesIO(content), "image/png"))


def test_upload_rejects_wrong_mimetype(client, auth_headers):
    sid = client.post("/api/v1/sessions", headers=auth_headers).json()["id"]
    resp = client.post(
        f"/api/v1/sessions/{sid}/receipt",
        headers=auth_headers,
        files=[("file", ("evil.txt", io.BytesIO(b"not an image"), "text/plain"))],
    )
    assert resp.status_code == 415


def test_upload_receipt_creates_row_and_file(client, auth_headers, tmp_path):
    sid = client.post("/api/v1/sessions", headers=auth_headers).json()["id"]
    resp = client.post(
        f"/api/v1/sessions/{sid}/receipt",
        headers=auth_headers,
        files=[_png_upload()],
    )
    assert resp.status_code == 201
    key = resp.json()["object_key"]
    # file physically landed in the (tmp) storage dir
    assert (tmp_path / "uploads" / key).exists()
    # session status advanced
    detail = client.get(f"/api/v1/sessions/{sid}", headers=auth_headers).json()
    assert detail["status"] == "RECEIPT_UPLOADED"
    assert len(detail["receipts"]) == 1
