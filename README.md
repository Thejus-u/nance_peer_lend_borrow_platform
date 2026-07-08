# Peer Lend and Borrow Platform (Nance)

This repository contains a working Django-based implementation of a peer lending and borrowing platform with Gmail transaction ingestion, discovered bank account suggestions, family ledger views, asynchronous notifications, and real-time WebSocket updates.

The README is intentionally implementation-first: it documents what is actually built in this codebase, calls out where behavior differs from assignment wording, and provides end-to-end local run instructions.

## 1. Overall Approach

The implementation is organized around clear domain boundaries and service-layer workflows:

1. Keep API views thin and route business rules through service classes.
2. Use transactional writes for state transitions (loan, repayment, family, notification).
3. Use append-only audit events for critical status changes.
4. Use Celery and Redis for asynchronous notification dispatch and scheduled overdue reminders.
5. Use Channels for authenticated real-time updates to lender and borrower clients.
6. Use Gmail OAuth + parsers to ingest savings/current account alerts and discover unlinked bank accounts.

At runtime the system is composed of:

1. Django ASGI API/web app
2. PostgreSQL database
3. Redis cache/broker/channel layer
4. Celery worker
5. Celery beat scheduler
6. WebSocket consumers for live loan/notification events

## 2. Scope and Feature Summary

Implemented in this repository:

1. User registration/login/logout and JWT refresh.
2. Loan creation with idempotency, accept/reject/cancel, and list/detail APIs.
3. Repayment creation/payment with overpayment protection and reconciliation confidence.
4. Family creation, invitations, accept/reject, member removal, and aggregated family ledger.
5. Gmail transaction ingestion with sender whitelisting and ignore filters.
6. Discovered bank account lifecycle: unlinked, linked, dismissed, unlinked.
7. Notification lifecycle with dedupe key support.
8. WebSocket events for loan and notification changes.
9. Health endpoint and deployment artifacts (Docker, ECS, PgBouncer assets).

## 3. Architecture

<p align="center">
  <img src="ECS_Cluster_Service-2026-07-08-194805.svg" width="900">
</p>

<p align="center">
<b>Figure 1. AWS Production Architecture(workflow)</b>
</p>

<p align="center">
  <img src="images(workflow)/aws_workflow.png" width="900">
</p>

<p align="center">
<b>Figure 2. AWS Production Architecture</b>
</p>

## 4. Tech Stack

Backend and runtime:

1. Django 5.2.2
2. Django REST Framework 3.16.0
3. SimpleJWT 5.4.0
4. PostgreSQL (local and AWS RDS)
5. Redis 7 (local and ElastiCache)
6. Celery 5.5.3
7. Channels 4.2.2 + channels-redis
8. Gunicorn + Uvicorn worker

Deployment assets:

1. Dockerfile
2. docker-compose.yml
3. PgBouncer files under infra/pgbouncer

## 5. Domain Modules

Core apps under src/apps:

1. accounts: identity, JWT auth endpoints, one Gmail integration path
2. loans: loan state transitions, repayments, websocket loan events
3. payments: bank transactions, discovered accounts, Gmail parser pipeline, reconciliation
4. family: family group and ledger context
5. notifications: queued and dispatched notifications
6. integrations: second Gmail integration path (OAuth callback/connect/status/sync)
7. audit: append-only state-change events
8. common: health endpoint and frontend route mapping

Scaffolded/placeholder modules with intentionally empty API routes in this stage:

1. marketplace
2. communications
3. risk
4. compliance

## 6. Assumptions

The implementation makes the following explicit assumptions:

1. Mobile number is the primary unique user identifier.
2. Loan payload includes richer fields than the assignment minimum (currency, interest, term, start and end dates).
3. Loan pending state is represented as pending_review or pending_invite rather than one literal pending_acceptance value.
4. Family model stores role-based membership and invitation workflows instead of relationship-label plus visibility fields.
5. Gmail parser relies on sender-domain whitelist plus rule-based parsing, not ML classification.
6. Reconciliation is best-effort matching with confidence levels; unmatched reference-driven payments are flagged for manual review.
7. WebSocket authentication uses JWT token in query string.
8. The repository currently contains two Gmail integration flows (accounts and integrations apps).

## 7. Data Model Overview

Key entities:

1. User: mobile_number, name, optional profile image
2. Loan: borrower, lender, principal, status, schedule metadata, source transaction reference
3. Repayment: installment, amount due/paid, status, optional transaction reference, match confidence
4. BankTransaction: debit/credit transaction records (manual or Gmail source)
5. DiscoveredAccount: inferred bank accounts from Gmail emails (status lifecycle)
6. Notification: channel, status, dedupe key, type, payload, sent/failure metadata
7. AuditEvent: append-only status transition records
8. Family, FamilyMember, FamilyInvitation, FamilyLedgerEntry

## 8. Loan Lifecycle and State Transitions

This section is mandatory per assignment, and reflects current implementation behavior.

Loan statuses available in code:

1. draft
2. pending_invite
3. pending_review
4. approved
5. rejected
6. disbursed
7. active
8. closed
9. cancelled

Important note:

1. Current code auto-closes a loan when all repayment rows are paid.
2. Assignment text says never auto-settle without user confirmation.
3. This is a known behavior mismatch to call out during evaluation.

## 9. Repayment and Balance Behavior

Repayment behavior implemented:

1. Create installment entries per loan.
2. Apply partial or full payment amounts atomically.
3. Reject overpayment attempts.
4. Mark repayment status as scheduled, partial, paid, or overdue.
5. Run daily overdue reminder task.

Balance concept follows:

1. Outstanding for installment = amount_due - amount_paid
2. Loan closes when no outstanding non-paid repayments remain

## 10. Gmail Savings/Current Account Parsing Approach

This section is mandatory per assignment.

The parser pipeline uses two layers:

1. Gate by trusted sender domain list (bank domain whitelist).
2. Run ignore parsers first, then transaction parsers.

Supported transaction styles in parser pipeline:

1. UPI
2. NEFT
3. RTGS
4. ATM
5. Generic debit
6. Generic credit

Parsed output includes:

1. Amount
2. Date/time (from Gmail metadata where available)
3. Direction (debit/credit)
4. Bank inference
5. Masked account hint
6. Reference ID when present
7. Description/narration
8. Account type inference (current keyword else savings)

## 11. How Credit Card Emails Are Excluded

This section is mandatory per assignment.

Exclusion is explicit and rule-driven in the Gmail parser pipeline. Ignore parsers run before transaction extraction.

Ignored categories include:

1. credit_card
2. emi
3. loan
4. marketing

Representative keyword signals include:

1. credit card
2. card statement
3. minimum due
4. emi
5. loan approved
6. promotional
7. cashback
8. pre-approved
9. unsubscribe

Additionally, sender whitelist filtering prevents parsing of mail from non-approved domains even if message text resembles transactions.

## 12. Gmail Sync and Discovery Flow

<p align="center">
  <img src="images(workflow)/Gmail_Ingestion_Service.svg" width="900">
</p>

<p align="center">
<b>Gmail Sync </b>
</p>

Discovered account behavior:

1. Account suggestion stored once per user-bank-account-type tuple.
2. supporting_email_count increments on repeated evidence.
3. Status transitions supported: unlinked, linked, dismissed, unlinked.
4. Dismissed accounts remain dismissed even when new matching emails arrive.

## 13. Transaction Reconciliation

Repayment-to-bank-transaction matching considers:

1. Exact amount
2. Direction must be debit
3. Date proximity window
4. Optional reference text in narration
5. Only linked savings/current discovered accounts

Confidence labels:

1. high
2. medium
3. low

Manual review:

1. If a transaction reference was provided but no suitable match is found, the repayment is flagged for manual review.

## 14. Notifications and Scheduling

Notification events are generated during workflow transitions, with dedupe support.

Produced notification types include:

1. loan_created
2. loan_accepted
3. loan_rejected
4. loan_cancelled
5. repayment_created
6. repayment_completed
7. loan_settled
8. repayment_overdue
9. family invitation and membership events

Scheduler behavior:

1. notifications.dispatch_pending runs every minute.
2. loans.send_overdue_reminders runs daily at 08:00.

## 15. Real-Time WebSocket Contract

Endpoint:

1. ws://host/ws/loans/?token=<jwt> (or wss on HTTPS)

Authentication and visibility:

1. JWT is required.
2. Events are published to per-user and per-loan groups.
3. Users only receive events for loans/notifications tied to their user ID.

Key event payload types:

1. connection_ack
2. loan_event
3. notification_event
4. ping/pong
5. subscription_ack and unsubscription_ack

Reconnect strategy returned in connection_ack:

1. enabled
2. strategy exponential_backoff_with_jitter
3. initial delay 1000 ms
4. max delay 30000 ms
5. max attempts 20

## 16. Security Model

Security controls implemented:

1. JWT bearer auth for APIs.
2. Refresh token blacklisting on logout.
3. Active-user permission checks for protected endpoints.
4. Participant-only access for loan detail.
5. Actor validation on accept/reject/cancel and family actions.
6. Idempotency and dedupe protections for critical side-effect operations.
7. Audit events for major state transitions.

Token-at-rest note:

1. integrations app stores encrypted Gmail tokens.
2. accounts app Gmail flow stores tokens without model-level encryption.
3. This dual-flow difference should be normalized in future cleanup.

## 17. API Surface (Implemented)

Primary endpoints:

1. GET /health/
2. POST /api/v1/accounts/auth/register/
3. POST /api/v1/accounts/auth/login/
4. POST /api/v1/accounts/auth/token/refresh/
5. GET /api/v1/accounts/auth/me/
6. POST /api/v1/accounts/auth/logout/
7. POST /api/v1/loans/
8. GET /api/v1/loans/list/
9. GET /api/v1/loans/incoming/
10. GET /api/v1/loans/lent/
11. GET /api/v1/loans/borrowed/
12. GET /api/v1/loans/active/
13. GET /api/v1/loans/settled/
14. GET /api/v1/loans/<id>/
15. POST /api/v1/loans/<id>/accept/
16. POST /api/v1/loans/<id>/reject/
17. POST /api/v1/loans/<id>/cancel/
18. POST /api/v1/loans/<loan_id>/repayments/
19. POST /api/v1/loans/repayments/<repayment_id>/pay/
20. GET /api/v1/payments/transactions/
21. POST /api/v1/payments/transactions/create/
22. GET /api/v1/payments/transactions/summary/
23. GET /api/v1/payments/discovered-accounts/
24. POST /api/v1/payments/discovered-accounts/discover/
25. POST /api/v1/payments/discovered-accounts/<account_id>/<action>/
26. POST /api/v1/family/create/
27. GET /api/v1/family/current/
28. GET /api/v1/family/current/ledger/
29. POST /api/v1/family/invitations/create/
30. GET /api/v1/family/invitations/
31. POST /api/v1/family/invitations/<id>/accept/
32. POST /api/v1/family/invitations/<id>/reject/
33. POST /api/v1/family/current/members/remove/
34. GET /api/v1/notifications/
35. POST /api/v1/notifications/create/
36. POST /api/v1/notifications/<id>/send/
37. POST /api/v1/notifications/<id>/fail/
38. Integrations Gmail endpoints under /api/v1/integrations/gmail/*
39. Accounts Gmail endpoints under /api/v1/accounts/auth/gmail/*

## 18. How to Run Locally

This section is mandatory per assignment.

### Option A: Native Python (Windows PowerShell)

1. Create and activate venv.

```powershell
cd D:\Nance
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies.

```powershell
pip install -r requirements.txt
```

3. Configure environment variables.

1. A root .env file is already used by the project.
2. Update values as needed for your local database, Redis, JWT, and Gmail credentials.

4. Start Postgres and Redis locally (Docker quick option).

```powershell
docker run --name peer-postgres -e POSTGRES_DB=peer_platform -e POSTGRES_USER=peer_user -e POSTGRES_PASSWORD=peer_pass -p 5432:5432 -d postgres:16
docker run --name peer-redis -p 6379:6379 -d redis:7
```

5. Run migrations and app.

```powershell
cd src
python manage.py migrate
python manage.py runserver
```

6. In separate terminals, start worker and beat.

```powershell
cd D:\Nance\src
..\.venv\Scripts\Activate.ps1
celery -A config worker --loglevel=INFO
```

```powershell
cd D:\Nance\src
..\.venv\Scripts\Activate.ps1
celery -A config beat --loglevel=INFO
```

7. Open local pages.

1. Frontend login: http://127.0.0.1:8000/app/login/
2. Admin: http://127.0.0.1:8000/admin/
3. Health: http://127.0.0.1:8000/health/

### Option B: Docker Compose

```powershell
cd D:\Nance
docker compose up --build
```

## 19. Seed Data and Demo

Seed command:

```powershell
cd D:\Nance\src
python manage.py seed_demo_data
```

Seed behavior:

1. Creates at least 3 users.
2. Creates mixed loan statuses including pending_review, pending_invite, active, rejected, cancelled, closed.
3. Creates repayment data to close one loan.
4. Creates demo Gmail account links.

API demo assets:

1. api-collections/Peer-Lend-Borrow.postman_collection.json
2. api-collections/bruno/*

## 20. Testing

Run full test suite:

```powershell
cd D:\Nance\src
python manage.py test --settings=config.settings.test
```

Coverage areas present in tests:

1. Authentication and JWT behavior
2. Loan create/accept/reject/cancel
3. Repayment create/pay and overpayment protection
4. Idempotency for loan and repayment create paths
5. Gmail parser and integration sync behavior
6. Discovered account actions and listing filters
7. Family invitation and ledger behavior
8. Notification API and task dispatch
9. Health endpoint status behavior
10. WebSocket JWT token auth helper behavior

## 21. Known Gaps and Assignment Alignment Notes

This section intentionally documents the current delta between code and assignment wording:

1. No single API.md file currently exists at repository root.
2. Placeholder apps marketplace/communications/risk/compliance expose empty API routes in this stage.
3. Auto-settle behavior for fully paid loans exists in code, while assignment guidance prefers explicit confirmation.
4. Family schema does not currently include relationship label and visibility preference fields from requirement wording.
5. Two Gmail integration paths exist, which can cause architecture overlap unless consolidated.
6. Root docs TESTING.md and DEMO_WALKTHROUGH.md are not present in current repository snapshot.

## 22. Deployment Summary

Deployment is documented in DEPLOY.md and is already operational in AWS with ECS, RDS, Redis, ALB, Route53, ACM, and PgBouncer.

Live production base URL:

1. https://thejus.fun

Health endpoint:

1. https://thejus.fun/health/

## 23. Repository Artifacts and Diagram References

Design and workflow visuals currently available include artifacts under images(workflow):

1. aws_workflow.png
2. Browser to Database Pipeline-2026-07-08-191814.svg
3. Django REST Service Pipeline-2026-07-08-191655.svg
4. Gmail Ingestion Service-2026-07-08-192757.svg
5. Idempotency Key Payment.svg

Primary documentation files:

1. DESIGN.md
2. DEPLOY.md
3. EXPLAIN.md
4. SECURITY.md
5. docs/architecture.md
6. docs/development-workflow.md
7. docs/api-testing.md

---

If you are evaluating this assignment, start with this order:

1. README.md for scope and behavior
2. EXPLAIN.md for requirement-by-requirement traceability
3. DESIGN.md for architecture and sequence diagrams
4. DEPLOY.md for production infrastructure and operations
5. Tests in src/apps/*/tests for executable evidence
