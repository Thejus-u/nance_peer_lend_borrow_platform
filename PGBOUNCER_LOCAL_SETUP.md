# PgBouncer Local Setup Guide for Nance

This document is a detailed reference for installing and configuring PgBouncer locally for this project.

Important scope note:

1. This guide does not change any project files.
2. This guide does not modify Docker Compose.
3. This guide does not modify Django settings.
4. This guide is meant for future enablement and local experimentation.

## 1. Introduction

### What PgBouncer is

PgBouncer is a lightweight PostgreSQL connection pooler. It sits between application clients (Django, workers, scripts) and PostgreSQL, and manages a pool of backend database connections.

Instead of every client process opening and holding its own PostgreSQL connection, clients connect to PgBouncer, and PgBouncer multiplexes these requests onto a controlled number of PostgreSQL server connections.

### Why connection pooling is useful

Connection pooling helps because:

1. PostgreSQL connections are expensive compared to lightweight client requests.
2. Web apps with multiple workers/processes can exhaust PostgreSQL max connections quickly.
3. Short-lived requests (common in APIs) do not need one dedicated DB connection each.
4. Pooling reduces connection churn and improves overall throughput and latency consistency.

### Why this project uses PgBouncer in production

This project runs multiple ECS services (web, worker, beat) that all talk to PostgreSQL. Pooling is useful to:

1. Protect RDS from connection spikes.
2. Keep connection usage predictable across services.
3. Improve resilience under load and during deploy rollouts.

The repository already includes PgBouncer assets under `infra/pgbouncer/` and production documentation in `DEPLOY.md`.

### Difference between direct PostgreSQL connections and PgBouncer

Direct PostgreSQL:

1. Django/worker connects directly to PostgreSQL on 5432.
2. Every app process contributes directly to DB connection count.
3. Connection scaling depends on DB limits.

PgBouncer path:

1. Django/worker connects to PgBouncer on 6432.
2. PgBouncer keeps a managed pool to PostgreSQL (5432).
3. DB sees fewer, controlled backend connections.

```mermaid
flowchart LR
    App[Django / Celery] -->|direct| PG[(PostgreSQL:5432)]
```

```mermaid
flowchart LR
    App[Django / Celery] --> PB[PgBouncer:6432]
    PB --> PG[(PostgreSQL:5432)]
```

---

## 2. Prerequisites

### Docker

You need Docker Desktop (or Docker Engine) installed and running.

Verify:

```powershell
docker version
```

### Docker Compose

You need Docker Compose support.

Verify:

```powershell
docker compose version
```

### PostgreSQL

For local setup in this repo, PostgreSQL is typically available through the existing local Docker workflow:

1. DB host: `localhost`
2. DB port: `5432`
3. DB name: `peer_platform`
4. DB user: `peer_user`

From current project compose defaults:

1. `POSTGRES_DB=peer_platform`
2. `POSTGRES_USER=peer_user`
3. `POSTGRES_PASSWORD=peer_pass`

### Existing project setup

Before testing PgBouncer locally, ensure project baseline runs:

1. Django app starts.
2. DB is reachable.
3. Redis is reachable.
4. Migrations can run.

Quick baseline checks:

```powershell
cd D:\Nance\src
python manage.py check
python manage.py migrate
python manage.py runserver
```

---

## 3. Local Installation

This section installs PgBouncer locally without changing existing project files.

### Docker image to use

The repo currently uses:

1. `edoburu/pgbouncer:latest`

You can use the same image locally for consistency.

### Required folders

Create a local PgBouncer workspace (example):

```text
D:\Nance\local-pgbouncer\
```

Inside it, create:

1. `pgbouncer.ini`
2. `userlist.txt`

### Example directory layout

```text
D:\Nance
|-- local-pgbouncer
|   |-- pgbouncer.ini
|   |-- userlist.txt
|-- infra
|   |-- pgbouncer
|       |-- pgbouncer.ini
|       |-- userlist.txt
|       |-- Dockerfile
```

### Required configuration files

Minimal local `pgbouncer.ini` example:

```ini
[databases]
peer_platform = host=host.docker.internal port=5432 dbname=peer_platform user=peer_user password=peer_pass

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432

auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt

pool_mode = transaction
max_client_conn = 200
default_pool_size = 20
reserve_pool_size = 5

ignore_startup_parameters = extra_float_digits

server_idle_timeout = 600
server_check_delay = 30
server_reset_query = DISCARD ALL

log_connections = 1
log_disconnections = 1

admin_users = peer_user
```

Minimal local `userlist.txt` example (MD5 mode):

```text
"peer_user" "md5<replace_with_md5_hash>"
```

Note: If PostgreSQL runs in another container network, use that container service name instead of `host.docker.internal`.

### Environment variables

You can run PgBouncer without extra env vars by mounting config files, but common optional variables include:

1. `TZ` (timezone)
2. `PGBOUNCER_CONFIG_FILE` (image-dependent)
3. `PGBOUNCER_AUTH_TYPE` (if image supports env-driven config)

For this project, file-driven config is preferred because `infra/pgbouncer` is file-based.

---

## 4. PgBouncer Configuration

Below are important options, what they do, and local development recommendations.

### listen_addr

What it does:

1. IP address PgBouncer binds to.

Recommended local value:

1. `0.0.0.0` inside container (so mapped host port works).

### listen_port

What it does:

1. PgBouncer listener port for client connections.

Recommended local value:

1. `6432` (standard PgBouncer port).

### auth_type

What it does:

1. Authentication method for client-to-PgBouncer auth.

Recommended local value:

1. `md5` for simple local compatibility.
2. `scram-sha-256` if your PostgreSQL/user setup is SCRAM-based and fully aligned.

### auth_file

What it does:

1. Path to user credentials file read by PgBouncer.

Recommended local value:

1. `/etc/pgbouncer/userlist.txt`.

### pool_mode

What it does:

1. Defines when backend server connections are returned to pool.

Recommended local value:

1. `transaction` (best default for Django workloads).

### max_client_conn

What it does:

1. Maximum simultaneous client connections PgBouncer accepts.

Recommended local value:

1. `100` to `300` for local dev.
2. Start with `200`.

### default_pool_size

What it does:

1. Max server connections per database/user pool.

Recommended local value:

1. `20` is a good default for local dev.

### reserve_pool_size

What it does:

1. Extra temporary connections for burst handling.

Recommended local value:

1. `3` to `5`, start with `5`.

### ignore_startup_parameters

What it does:

1. Ignores client startup params PgBouncer does not need.

Recommended local value:

1. `extra_float_digits` (common with PostgreSQL clients).

### server_idle_timeout

What it does:

1. Closes idle server connections after N seconds.

Recommended local value:

1. `600` (10 minutes) for local.

### server_check_delay

What it does:

1. Delay between backend connection health checks.

Recommended local value:

1. `30` seconds.

### server_reset_query

What it does:

1. SQL run when server connection is released to pool.

Recommended local value:

1. `DISCARD ALL` for clean session state.

### log_connections

What it does:

1. Logs client connect events.

Recommended local value:

1. `1` (enabled) for troubleshooting.

### log_disconnections

What it does:

1. Logs client disconnect events.

Recommended local value:

1. `1` (enabled) for troubleshooting.

---

## 5. Authentication

### userlist.txt

`userlist.txt` maps PgBouncer usernames to secrets. Format:

```text
"username" "secret_or_hash"
```

For MD5 mode, secret format is:

```text
md5<md5(password + username)>
```

### MD5 password generation

PowerShell example for user `peer_user` with password `peer_pass`:

```powershell
$plain = "peer_passpeer_user"
$md5 = [System.Security.Cryptography.MD5]::Create()
$bytes = [System.Text.Encoding]::UTF8.GetBytes($plain)
$hash = ($md5.ComputeHash($bytes) | ForEach-Object { $_.ToString("x2") }) -join ""
"md5$hash"
```

Then put in `userlist.txt`:

```text
"peer_user" "md5<generated_hash>"
```

### SCRAM authentication

If using `auth_type = scram-sha-256`:

1. PostgreSQL user must have SCRAM verifier.
2. PgBouncer must support SCRAM mode and compatible auth_query/auth_file behavior.
3. Client auth and backend auth must align.

SCRAM is stronger than MD5 and preferred for production when fully configured.

### How PostgreSQL users authenticate through PgBouncer

Path:

1. Client authenticates to PgBouncer using `auth_type` and `userlist.txt`.
2. PgBouncer authenticates to PostgreSQL using credentials in `[databases]` or mapped mechanisms.
3. PostgreSQL validates user/password under its own auth rules (`pg_hba.conf`, password method, etc.).

---

## 6. Docker Example

This is an example snippet only. It is not a modification to current `docker-compose.yml`.

```yaml
services:
  pgbouncer:
    image: edoburu/pgbouncer:latest
    container_name: peer_platform_pgbouncer
    restart: unless-stopped
    ports:
      - "6432:6432"
    volumes:
      - ./local-pgbouncer/pgbouncer.ini:/etc/pgbouncer/pgbouncer.ini:ro
      - ./local-pgbouncer/userlist.txt:/etc/pgbouncer/userlist.txt:ro
    healthcheck:
      test: ["CMD-SHELL", "nc -z localhost 6432 || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5
```

If your DB runs as Docker service in same compose network, set database host in `pgbouncer.ini` to DB service name (for example `db`).

---

## 7. Django Configuration

This section explains how Django would connect through PgBouncer if enabled later. It does not instruct changing this project now.

Current pattern in project:

1. Django reads `DATABASE_URL` from environment.

PgBouncer-style `DATABASE_URL` example:

```text
postgres://peer_user:peer_pass@localhost:6432/peer_platform
```

Equivalent Django `DATABASES` example:

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "peer_platform",
        "USER": "peer_user",
        "PASSWORD": "peer_pass",
        "HOST": "localhost",
        "PORT": "6432",
        "CONN_MAX_AGE": 0,
    }
}
```

Suggested environment variables for PgBouncer-enabled mode:

1. `DATABASE_URL` pointing to `localhost:6432`
2. Optional `DB_CONN_MAX_AGE=0` when using transaction pooling

Why `CONN_MAX_AGE=0` is often used with transaction pooling:

1. It avoids long-lived Django-held connections and lets PgBouncer manage pooling more effectively.

---

## 8. Health Checks

Ways to verify PgBouncer health:

### Container health

```powershell
docker ps
```

Look for PgBouncer container as `healthy` (if healthcheck configured).

### Port reachability

```powershell
Test-NetConnection -ComputerName localhost -Port 6432
```

Expected:

1. `TcpTestSucceeded : True`

### PgBouncer admin ping via psql

```powershell
psql "host=localhost port=6432 dbname=pgbouncer user=peer_user password=peer_pass" -c "SHOW VERSION;"
```

Expected:

1. Returns PgBouncer version row.

---

## 9. Verification Commands

Connect to PgBouncer admin database:

```powershell
psql "host=localhost port=6432 dbname=pgbouncer user=peer_user password=peer_pass"
```

Then run:

```sql
SHOW POOLS;
SHOW CLIENTS;
SHOW SERVERS;
SHOW STATS;
```

### Expected output interpretation

`SHOW POOLS;`

1. Shows one row per (database, user) pool.
2. Key fields include active/waiting clients and active/idle servers.

`SHOW CLIENTS;`

1. Shows currently connected client sessions.
2. Useful to confirm app clients are entering PgBouncer.

`SHOW SERVERS;`

1. Shows backend PostgreSQL connections managed by pooler.
2. Count should be lower and steadier than raw client count under load.

`SHOW STATS;`

1. Aggregated stats like requests, wait times, bytes in/out.
2. Helps validate pooling effectiveness and detect pressure.

---

## 10. Pool Modes

### Session pooling

1. Server connection assigned to client for entire client session.
2. Highest compatibility, lowest multiplexing efficiency.

### Transaction pooling

1. Server connection assigned only for each transaction.
2. Better reuse and typically best trade-off for web apps.

### Statement pooling

1. Server connection assigned per statement.
2. Highest multiplexing, lowest compatibility.

### Why Transaction mode is generally recommended for Django

Transaction mode is usually recommended because:

1. Django workloads are request/transaction oriented.
2. It provides strong pooling efficiency with good compatibility.
3. It avoids many session-state pitfalls of statement mode.

Caveat:

1. Features relying on long session state (temporary tables, session-level settings across transactions) need careful review.

---

## 11. Troubleshooting

### Authentication failures

Symptoms:

1. `password authentication failed`
2. `no such user`

Diagnosis:

1. Check `userlist.txt` formatting.
2. Verify username exactly matches client user.
3. Verify MD5 hash formula uses `password + username`.
4. Check `auth_type` compatibility.

Resolution:

1. Regenerate hash carefully.
2. Restart PgBouncer container after userlist changes.
3. Align PgBouncer auth mode with your credential type.

### PostgreSQL connection failures

Symptoms:

1. PgBouncer can start, but app queries fail.
2. `server login failed` or `could not connect to server`.

Diagnosis:

1. Test direct DB connectivity from host/container.
2. Validate DB host/port in `[databases]` entry.
3. Validate DB username/password.

Resolution:

1. Fix host routing (`host.docker.internal` vs compose service name).
2. Confirm DB is running and accepting connections.
3. Confirm PostgreSQL auth rules permit that user.

### Pool exhaustion

Symptoms:

1. Increased wait times.
2. Clients queueing in `SHOW POOLS`.

Diagnosis:

1. Check `cl_waiting`, `sv_active`, `sv_idle` in `SHOW POOLS`.
2. Compare with `default_pool_size` and DB max connections.

Resolution:

1. Increase pool size cautiously.
2. Tune app concurrency.
3. Ensure DB max connections can support pool limits.

### Health check failures

Symptoms:

1. Container marked unhealthy.

Diagnosis:

1. Inspect logs: `docker logs <pgbouncer-container>`.
2. Validate healthcheck command exists in image.

Resolution:

1. Use simple TCP healthcheck first.
2. Switch to psql-based healthcheck once stable.

### Docker networking problems

Symptoms:

1. PgBouncer cannot reach DB container.

Diagnosis:

1. Confirm both services are in same Docker network.
2. Inspect network: `docker network inspect <network-name>`.

Resolution:

1. Use correct service DNS name when in same network.
2. Use `host.docker.internal` only when DB is on host side.

---

## 12. Best Practices

### Pool sizing

Use a top-down budget:

1. Start with PostgreSQL `max_connections`.
2. Reserve headroom for admin/maintenance.
3. Allocate PgBouncer pools conservatively across services.

### Memory considerations

1. `max_client_conn` impacts client-side memory overhead.
2. Avoid setting very high client limits without need.

### Connection limits

1. Keep `default_pool_size` realistic per service profile.
2. Avoid aggregate pool sizing that exceeds DB capacity.

### Logging

1. Enable connection/disconnection logs in local debugging.
2. In production, tune verbosity to avoid log noise.

### Monitoring

Track regularly:

1. `SHOW STATS` trends.
2. Waiting clients.
3. Backend server utilization.
4. Connection errors and auth failures.

### Production recommendations

1. Prefer secure auth (`scram-sha-256`) where possible.
2. Avoid plaintext credentials in committed files.
3. Use secrets managers for credentials.
4. Keep pool_mode as `transaction` unless a proven reason exists.
5. Perform load tests before changing pool limits.

---

## 13. Local Testing

Goal: prove the application traffic goes through PgBouncer.

### Step 1: Establish baseline direct DB count

Connect directly to PostgreSQL and run:

```sql
SELECT count(*) AS direct_connections
FROM pg_stat_activity
WHERE datname = 'peer_platform';
```

### Step 2: Point test client to PgBouncer

Use a PgBouncer connection string in your test client:

```text
postgres://peer_user:peer_pass@localhost:6432/peer_platform
```

### Step 3: Generate application activity

Examples:

1. Open app pages that hit DB.
2. Call loan list/details APIs.
3. Run a small script issuing repeated queries.

### Step 4: Inspect PgBouncer admin views

Run:

```sql
SHOW CLIENTS;
SHOW SERVERS;
SHOW POOLS;
SHOW STATS;
```

Expected signs:

1. `SHOW CLIENTS` includes your app/test clients.
2. `SHOW SERVERS` remains bounded near pool size, not exploding with client count.
3. `SHOW POOLS` may show many clients with fewer active servers under burst.

### Step 5: Confirm DB sees PgBouncer-origin connections

On PostgreSQL:

```sql
SELECT application_name, usename, client_addr, state, count(*)
FROM pg_stat_activity
WHERE datname = 'peer_platform'
GROUP BY application_name, usename, client_addr, state
ORDER BY count(*) DESC;
```

Interpretation:

1. You should see stable backend connection counts from PgBouncer host/container path.
2. Connection growth should be flatter than direct-app mode.

---

## Appendix: Project-Specific Reference Values (Current State)

Observed in repository assets today:

1. PgBouncer listen port: `6432`
2. Production-style pool mode: `transaction`
3. Current local PostgreSQL compose defaults:
4. DB name: `peer_platform`
5. DB user: `peer_user`
6. DB password: `peer_pass`
7. DB port: `5432`

Current `infra/pgbouncer/pgbouncer.ini` uses `auth_type = plain` with a plaintext `userlist.txt`.
For local learning and safer patterns, this guide demonstrates MD5/SCRAM options.
