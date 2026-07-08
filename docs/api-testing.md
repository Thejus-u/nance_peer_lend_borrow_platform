# API Testing Guide

This guide reflects the corrected workflow:
- Lender creates the loan request.
- Borrower receives incoming requests.
- Borrower accepts or rejects.
- Accepted loan becomes `active`.

## Collections

- Postman: `api-collections/Peer-Lend-Borrow.postman_collection.json`
- Bruno: `api-collections/bruno/`

## Required Setup

1. Start backend (`python manage.py runserver` or `docker compose up --build`).
2. Create lender and borrower users.
3. Login both users and keep both JWT access tokens.

## Core Endpoints

- Create loan (lender): `POST /api/v1/loans/`
- Incoming requests (borrower): `GET /api/v1/loans/incoming/`
- Accept (borrower): `POST /api/v1/loans/{loan_id}/accept/`
- Reject (borrower): `POST /api/v1/loans/{loan_id}/reject/`
- Cancel (lender, pre-acceptance): `POST /api/v1/loans/{loan_id}/cancel/`

## Suggested Test Flow

1. Register lender and borrower.
2. Login lender and borrower.
3. Lender creates loan with `borrower_id`.
4. Borrower calls incoming endpoint and confirms request visibility.
5. Borrower accepts request -> verify status is `active`.
6. Repeat with a fresh loan and reject path.
7. Verify lender cancel works before borrower decision and fails after acceptance.

## Query Endpoints

- `GET /api/v1/loans/incoming/`
- `GET /api/v1/loans/lent/`
- `GET /api/v1/loans/borrowed/`
- `GET /api/v1/loans/active/`
- `GET /api/v1/loans/settled/`

## Family Module

- Create family: `POST /api/v1/family/`
- Add member: `POST /api/v1/family/{family_id}/members/add/`
- Remove member: `POST /api/v1/family/{family_id}/members/remove/`
- Ledger: `GET /api/v1/family/{family_id}/ledger/`

### Family Creation Workflow

1. Call create family with body:

```json
{
	"name": "My Family"
}
```

2. Verify response is `201` with `id`, `name`, `created_by`, `created_at`.
3. Verify creator is automatically inserted into `family_familymember` with role `owner`.
4. Immediately call family ledger endpoint using new `family_id` and verify `200` response.

## Notifications Lifecycle

Automatic notifications are now created via existing Celery task integration during service workflows.

### Auto-Generated Events

- `loan_created`
- `loan_accepted`
- `loan_rejected`
- `loan_cancelled`
- `repayment_created`
- `repayment_completed`
- `loan_settled`

### Notification APIs

- List notifications: `GET /api/v1/notifications/`
- Detail notification: `GET /api/v1/notifications/{notification_id}/`
- Create manual notification: `POST /api/v1/notifications/create/`
- Mark sent: `POST /api/v1/notifications/{notification_id}/send/`
- Mark failed: `POST /api/v1/notifications/{notification_id}/fail/`

### Verification Steps

1. Execute loan lifecycle APIs and repayment APIs.
2. Query `GET /api/v1/notifications/` for recipient users.
3. Verify `notification_type` and `is_read` fields in responses.
4. Validate persisted records in `notifications_notification` and audit logs in `audit_auditevent`.

## WebSocket Real-Time Testing

WebSocket endpoint: `ws://<host>/ws/loans/?token=<access_token>` (or `wss://` on HTTPS).

1. Open two browser sessions and login as lender and borrower.
2. Navigate to loan list and/or loan detail pages.
3. Trigger events (create, accept, reject, cancel) from one user.
4. Verify the other user page updates without manual refresh.
5. Verify notifications page updates automatically when notification events are emitted.

## Celery Worker and Beat Verification

1. Ensure worker and beat are running.
2. Create a workflow event that generates notifications (loan lifecycle or repayment).
3. Verify worker logs show task execution for:
	- `notifications.queue_notification`
	- `notifications.dispatch_pending`
4. Verify notifications transition from `pending` to `sent` automatically without pressing Send.
5. Verify beat dispatch schedule is active (every minute).
