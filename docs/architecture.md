# Architecture - Stage 1

## Design Goals

- Keep domain modules isolated for independent scaling and ownership.
- Keep views thin by routing business workflows through a service layer.
- Keep read and write paths explicit through selectors and services.
- Keep infrastructure concerns centralized in config settings.
- Keep security and operational concerns explicit in environment-driven settings.

## Folder Structure

```
.
|-- Dockerfile
|-- docker-compose.yml
|-- requirements.txt
|-- .env.example
|-- docs/
|   |-- architecture.md
|   |-- development-workflow.md
|-- scripts/
|   |-- start-web.sh
|   |-- start-worker.sh
|   |-- start-beat.sh
|-- src/
	 |-- manage.py
	 |-- config/
	 |   |-- __init__.py
	 |   |-- asgi.py
	 |   |-- celery.py
	 |   |-- routing.py
	 |   |-- urls.py
	 |   |-- wsgi.py
	 |   |-- settings/
	 |       |-- __init__.py
	 |       |-- base.py
	 |       |-- local.py
	 |       |-- production.py
	 |-- apps/
		  |-- common/
		  |-- accounts/
		  |-- marketplace/
		  |-- loans/
		  |-- payments/
		  |-- communications/
		  |-- risk/
		  |-- compliance/
		  |-- audit/
		  |-- integrations/
```

## Service Layer Convention

Each Django app follows this package convention:

- api/: serializers, validators, DRF views/viewsets, and route declarations.
- services/: write-side use cases and transactional orchestration.
- selectors/: read-side query logic for efficient retrieval and composition.
- repositories/: persistence abstraction for complex data access patterns.

This creates clear separation of concerns:

- API layer handles transport concerns only.
- Service layer executes business workflows and transaction boundaries.
- Selector/repository layer handles data-fetch strategy.

## Django Apps and Why They Exist

1. common
	Shared cross-cutting utilities, shared exceptions, and reusable platform primitives.

2. accounts
	Identity, authentication integration points, and user profile boundaries.

3. marketplace
	Discovery-facing listing and offer surfaces for lender and borrower interactions.

4. loans
	Loan lifecycle boundary (application, approval flow, state transitions).

5. payments
	Payment orchestration, disbursement scheduling, and ledger integration boundary.

6. communications
	Notification and conversation channels (email, in-app, websocket/chat).

7. risk
	Risk rules, eligibility scoring interfaces, and fraud-control boundary.

8. compliance
	Policy controls, KYC/AML orchestration boundaries, and regulatory workflow support.

9. audit
	Immutable audit event boundary for cross-domain traceability and forensics.

10. integrations
	 External provider adapter boundary (payment rails, KYC vendors, credit agencies, messaging providers).

## Transaction Strategy

- Service methods that write across multiple models or bounded contexts must use atomic transactions.
- `ATOMIC_REQUESTS` is enabled at the DB level as a safe default for write consistency.
- Explicit `transaction.atomic()` blocks should still be used in services for complex multi-step workflows.

## Scalability Notes

- Channels and Celery are configured from day one to avoid invasive refactoring later.
- App boundaries map to future team ownership and potential extraction points.
- `integrations` isolates provider-specific churn from core domain modules.
- Environment-driven settings allow consistent runtime behavior across local, CI, and production.
