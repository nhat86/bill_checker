# Development Learning Log — Grocery Receipt Auditor

Personal learning record for the `bill_checker` project. Updated after every task.

## Project goal

Mobile-first web app that audits French supermarket receipts: compares what you
actually bought vs. what you were charged, and detects promotions that should
have been applied but weren't.

Core rule: **AI extracts data, deterministic Python decides.** An LLM never
decides whether money is owed — it only reads images/text. All financial
verdicts come from testable Python engines.

---

## Task 1 — Repository inspection & architecture (current)

### Current state

Greenfield repo. Scaffolded so far (no code executed yet):

| Path | Purpose |
|---|---|
| `docker-compose.yml` | Orchestrates postgres, redis, minio, api, web |
| `.env.example` | Template for all config/secrets (never commit `.env`) |
| `.gitignore` | Python/Node/env/OS artifacts |
| `backend/pyproject.toml` | Python deps + project metadata |
| `backend/Dockerfile` | API container image |
| `backend/app/core/config.py` | Pydantic-settings: env vars → typed config |
| `backend/app/core/db.py` | SQLAlchemy engine + session factory + `Base` |
| `backend/app/core/security.py` | PBKDF2 password hashing + JWT issue/verify |
| `backend/app/models/` | ORM models: users, retailers, stores, products, catalogues, promotions, sessions, receipts, findings |
| `backend/app/schemas/` | Pydantic API contracts (request/response shapes) |
| `backend/app/services/storage.py` | Storage abstraction: MinIO or local filesystem |

Not yet built: API routers, `main.py`, Alembic migrations, tests, frontend.

### Key concepts learned so far

- **Layered architecture**: routers (HTTP) → services (infra/AI) → engines
  (business rules) → models (DB). Dependencies point inward; engines never
  import FastAPI.
- **Models vs schemas**: SQLAlchemy models = DB shape; Pydantic schemas = API
  shape. Keeping them separate lets the DB change without breaking the API.
- **`JSONB().with_variant(JSON(), "sqlite")`**: portable column type — real
  JSONB in production Postgres, plain JSON in SQLite tests.
- **PBKDF2 over bcrypt**: stdlib-only password hashing (no native deps,
  works on Python 3.14), 600k iterations, per-user salt, constant-time compare.
- **JWT**: stateless auth token signed with `SECRET_KEY`; contains `sub`
  (user id) + expiry. Server verifies signature — no session table needed.
- **Storage abstraction**: files addressed by opaque keys, never public URLs —
  receipts are private data.

### Deep dive completed: Docker Compose

- Container = isolated process from an image; Compose = declarative
  orchestration of the whole stack.
- `ports: HOST:CONTAINER` — inside the network services use names (`db:5432`),
  from Windows you use `localhost:5432`. "localhost" = whoever asks.
- `POSTGRES_*` env vars initialize only on first boot (empty data dir).
- Named volumes persist data; `down` keeps them, `down -v` wipes the DB.
- `depends_on` alone ≠ ready — `condition: service_healthy` waits for the
  healthcheck (pg_isready / redis-cli ping / mc ready).
- `env_file` loads `.env`; `environment:` keys override it — compose pins
  container-network URLs that differ from host URLs.
- Bind mounts (`./backend:/app`) give live reload; dependencies are baked at
  image build → `docker compose build` after changing pyproject/package.json.
- `/app/node_modules` anonymous volume keeps Linux-built deps alive while the
  host folder is mounted over `/app`.
- MinIO = self-hosted S3: port 9000 API, 9001 console; DB stores keys, not blobs.

### Open questions / decisions

- Auth is JWT-bearer (simple, mobile/PWA-friendly). Refresh tokens deferred.
- Async jobs: FastAPI `BackgroundTasks` for now; Celery+Redis later.
- Next task candidates: (a) finish minimal API (routers + main.py) so backend
  runs, or (b) git init + first commit to protect current work.

### Commands reference (so far)

```bash
docker compose up -d db redis minio   # infra only
pip install -e "backend/[dev]"        # backend deps (local dev)
uvicorn app.main:app --reload         # run API (once main.py exists)
```
