# Operations

War-time runbook for ServiceDesk. Written during Phase 7 of the
improve-code-quality journey (release-it); update it whenever the
deployment topology changes.

## Topology

- `web` — Flask app served by **gunicorn** (entrypoint runs `flask db upgrade`
  before starting, so schema migrations apply on every deploy; `SKIP_MIGRATIONS=true`
  to skip once).
- `db` — PostgreSQL 16 (persistent volume). Redis for rate-limit storage /
  future Celery workers. `nginx` optional TLS reverse-proxy (`--profile proxy`).
- All-in-one image (`Dockerfile.alpine`) runs embedded nginx + gunicorn on
  unprivileged `:8080`; TLS terminates at an external proxy of your choosing.
- Local dev: SQLite, `python run.py`. Production: PostgreSQL per `README.md`.

## Capacity model

Target: **~50 employees**, a handful of concurrent agents.

- Headroom is large: the app is a single sync Flask process; Postgres is the
  only stateful dependency. At this scale the bottleneck is never request
  throughput — it is an unreturned call *inside* a request (SMTP, external
  lookup) tying up a worker.
- Mitigations already in place:
  - `MAIL_TIMEOUT` (default 10s) caps SMTP hangs; sends are async-able
    (`MAIL_ASYNC`).
  - `MAX_CONTENT_LENGTH` enforced in-app (not just at the proxy) → uploads
    capped, oversized requests get a friendly 413, not a hung upload.
  - Rate limits (`default_limits` on `limiter` in `app/__init__.py`) bound
    per-IP abuse.
- **Scale trigger:** split-boundary pressure (failures/latency at >200
  concurrent agents, or rate-limit storage contention) → move rate-limit
  storage to Redis (`RATELIMIT_STORAGE_URI`), then consider gunicorn workers
  per core. No circuit breakers/bulkheads until a second outbound dependency
  exists (sole dependency is the DB; that is Postgres's job).

## Load smoke

`scripts/load_smoke.py` (stdlib only) fires GETs at one endpoint and reports
throughput, failures, and p50/p95 latency:

```bash
python scripts/load_smoke.py --url http://localhost:5000/ready --requests 100 --workers 25
```

Baseline (dev machine, gunicorn `-w 4 --threads 2`, SQLite, rate-limit ceiling
not exceeded), recorded 2026-10-08:

| Endpoint | req/s | p50 | p95 | failures |
|---|---|---|---|---|
| `/ready` (deep DB check) | ~2 594 | 5 ms | 19 ms | 0 |
| `/health` | ~2 617 | 2 ms | 10 ms | 0 |

Caveats:
- **Do not run above the per-IP rate ceiling** (default `200 per day`) — the
  limiter starts answering 429 at ~0.4 ms each and the script counts them as
  failures. Run against a fresh instance, or raise the limit for the test IP.
- Anything starting with `https` is probed without TLS verification
  (terminator sits in front; the app behind it answers plain HTTP).
- Not a benchmark. It is a "does this deploy serve requests, at what rough
  capacity" gate. Run it on the box *and through the proxy* once per deploy.

## Deploy

1. Build image; `docker compose up -d --build` (entrypoint applies migrations).
2. Health check the container:
   - `GET /health` → 200 (liveness, exempt from setup gate).
   - `GET /ready` → 200 (`SELECT 1` against Postgres; 503 on DB failure).
3. Run the load smoke against the live port and through the proxy; confirm
   failures = 0 and p95 does not blow out vs baseline.
4. Smoke one real workflow as a user (login → view ticket), not just the
   health endpoints — the health surface never touches the app stack in depth.
5. Watch `gunicorn` access/error logs for the first hour for 5xx spikes.

## Rollback

- New deploy is an image swap + `flask db upgrade`. Rollback = restart the
  previous image.
- **Migrations are append-only.** Down-migrations are not relied on for
  rollback; if a release carries a breaking migration, launch with the old
  image pinned *at the old schema* (do not run `flask db upgrade` on the new
  image against data the old one still writes).
- Health gates above decide "keep this image or flip back": a `ready` 503 or
  a spike of 5xxs while requests drain → roll back.

## Monitoring

Current surface (deemed sufficient at this scale):
- **Health prober** hitting `/health` + `/ready` (external uptime checks,
  or `docker compose` healthcheck). `/ready` is the one that matters — it
  exercises Postgres.
- **gunicorn access + error logs** (rotate; forward to wherever the operator
  reads logs). Grep for `Traceback` / `ERROR` / `429`.
- SMTP failures already log a clear hint (`_smtp_error_hint`) — they are
  actionable operator errors, so they surface in logs, not only in user-facing
  flashes.

Deferred: structured telemetry (OpenTelemetry/prometheus) — add when there is
a second service to correlate with, not before.

## Phase 7 (release-it) diagnostic — 8 rows

1. **Timeouts** — real. `MAIL_TIMEOUT` caps SMTP. External lookups: none.
2. **Circuit breakers** — N/A by scope: sole outbound dependency is the DB.
3. **Bulkheads** — N/A: single process, one DB; worker pool bounds itself.
4. **Zero-downtime deploys** — infra decision, recorded above (image swap +
   append-only migrations). Not in app code.
5. **Deep health** — real: `/ready` does `SELECT 1` → 200/503.
6. **Telemetry** — deferred (access logs suffice at this scale; add
   OpenTelemetry when a second service appears).
7. **Load handling** — load smoke script + baselines above.
8. **Failure injection** — N/A single-process; the equivalent is the
   characterization suite (`tests/`), which pins the failure modes we know.