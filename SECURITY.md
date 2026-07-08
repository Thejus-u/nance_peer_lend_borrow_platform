# SECURITY

## Authentication

- JWT bearer authentication using SimpleJWT.
- Login issues access and refresh tokens.
- Refresh endpoint rotates access token based on refresh token.
- Logout blacklists refresh token.

## Authorization

- API endpoints use authenticated-active permission checks.
- Loan detail endpoint enforces participant/staff access.
- Loan accept/reject is borrower-scoped.
- Loan cancel is lender-scoped.
- Discovered account actions are owner-scoped.

## WebSocket Security

- WebSocket authentication required.
- Unauthenticated or inactive users are rejected.
- Events are published to per-user groups (`loan_user_{id}`), limiting event visibility.

## Idempotency and Duplicate Protection

- Loan create/accept/reject/cancel flows support idempotency keys at service layer.
- Notification creation supports `dedupe_key` to prevent duplicate records.
- Gmail synced emails are unique per Gmail account and message ID.
- Gmail-ingested bank transactions are deduped by user + source + raw Gmail message reference.

## Gmail Ingestion Safety Controls

- Sender-domain whitelist gates parsing for bank emails.
- Ignore filters block credit card, EMI/loan, and promotional/cross-sell emails.
- Only linked savings/current accounts are eligible for repayment reconciliation matching.

## Auditability

- Critical state changes are recorded in append-only audit events.
- Includes loan lifecycle, repayment status, discovered-account status, notification status, and Gmail parse outcomes.
