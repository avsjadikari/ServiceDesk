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

**Estimate (back-of-envelope, Phase 8):**
- QPS: 50 users × 30 actions/day ÷ 86 400 s ≈ **0.02 req/s avg**, ~0.1 at 5×
  peak. Measured single-instance throughput (below) is ~2 600 req/s — 4 to 5
  orders of magnitude of headroom. No caching needed at this volume (row 5 of
  the diagnostic).
- Storage: ~5 KB per recorded action × ~1 500 actions/day ≈ **7.5 MB/day,
  ~2.7 GB/yr** — trivial for Postgres. Attachments go to disk, not the DB.

**Concurrency / backpressure:**
- The app is a single sync Flask process (gunicorn `gthread`,
  `GUNICORN_WORKERS` default 3-4 × `GUNICORN_THREADS` 2 → **6-8 concurrent
  requests**). Gunicorn's socket backlog (default 2048) overflow-queues the
  rest; combined with the rate limiter, in-flight work is bounded.
- SLA/automation/audit work happens inside the request. Long SMTP sends are
  capped by `MAIL_TIMEOUT` and can be pushed to a daemon thread
  (`MAIL_ASYNC`); that is the only async path that exists on purpose.
- **Scale trigger:** sustained latency regression while worker CPU is low
  (i.e. requests waiting, not computing) → raise `GUNICORN_WORKERS`/`THREADS`
  first; move rate-limit storage to Redis (`RATELIMIT_STORAGE_URI`) if limiter
  lock contention appears; add a second web container only past that.

**Database pool:**
- SQLAlchemy defaults: `pool_size=5`, `max_overflow=10` per worker process.
  3-4 gunicorn workers → up to **~20 idle, ~60 worst-case Postgres
  connections**, under the default `max_connections=100`. Leave defaults;
  raise `pool_size` only with the worker count.
- `pool_pre_ping` + `pool_recycle` already handle stale connections.

**Rate limiter (login path audit, Phase 8):**
- Auth routes carry dedicated per-IP limits — `login` 5/min, `login_2fa`
  10/min, `forgot_password` 3/min — layered over the global
  `200/day`/`50/hour` defaults. Distributed brute-force (IP rotation) is
  stopped by the in-app account lockout (`LOGIN_MAX_ATTEMPTS`/lockout minutes)
  per account. Combination is adequate at this deployment; revisit only if the
  app is ever exposed to the public internet.

**Availability (RPO/RTO):**
- NFR baseline: **99.9% ~ 8.8 h/yr** — matches single-instance reality.
- Single Postgres volume: RPO = last backup, RTO = restore + container
  start (minutes). Minimum viable backup — a cron'd `pg_dump` to an off-host
  location, hourly:
  `0 * * * * docker exec $(docker compose ps -q db) pg_dump -U servicedesk servicedesk | gzip > /backups/servicedesk-$(date +\%F-\%H).sql.gz`
  (Retention: keep 48 h hourly + daily; verify restorability quarterly by
  restoring into a scratch container.)

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

## Phase 8 (system-design) diagnostic — 8 rows

1. **Requirements** — listed: functional (tickets, SLA, assets, KB, analytics,
   portal) + NFR (50 users, <1 s p95, 99.9%, 8.8 h/yr).
2. **QPS/storage estimate** — real (above): ~0.02 avg / 0.1 peak req/s,
   ~7.5 MB/day. Four to five orders of magnitude below measured capacity.
3. **Redundancy** — single web + single Postgres by scope. Honest position:
   no multi-AZ at 50 users; failure budget covered by RPO/RTO above and
   health-gated rollback. Add replicas only when downtime per year > 8.8 h.
4. **DB scaling strategy** — vertical first; pool/workers sized (above;
   ~60 conns max < 100 default); SQLite→Postgres migration path documented in
   README. Shard only when single-node Postgres is the measured bottleneck.
5. **Cache for read-heavy paths** — none, and none warranted at 0.02 req/s.
   Introduce cache-aside (Redis) only when the slowest list view becomes a
   measured problem.
6. **Async via queues** — SMTP async path exists (daemon thread +
   `MAIL_ASYNC`). No queue broker until email is not the only async job.
7. **Monitoring/alerting** — `/health` + `/ready` probes, gunicorn access
   logs, SMTP-failure hint logging. Telemetry deferred (documented).
8. **Deployment strategy** — image swap + append-only migrations; rollback =
   old image pinned at old schema; health gates after deploy. Documented above.

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