# Development Workflow - Stage 1

## 1. Environment Bootstrapping

1. Copy `.env.example` to `.env`.
2. Keep secrets out of source control.
3. Use `config.settings.local` for local and `config.settings.production` for deployment.

## 2. Run with Docker Compose

1. Start full stack:

	docker compose up --build

2. Services started:

	- web (Django + ASGI)
	- db (PostgreSQL)
	- redis
	- worker (Celery)
	- beat (Celery scheduler)

## 3. Service Layer Development Rules

1. Keep DRF views thin: parse request, call service, return response.
2. Place write workflows in `services/`.
3. Place read/query composition in `selectors/`.
4. Keep side effects (emails, async jobs, notifications) out of views.

## 4. Configuration Rules

1. All runtime configuration must come from environment variables.
2. Never hardcode secrets in code.
3. Keep base settings shared and environment-specific overrides minimal.

## 5. Background Processing Rules

1. Use Celery workers for non-blocking operations.
2. Use Celery Beat for periodic jobs.
3. Keep task payloads small and serializable.

## 6. Realtime Rules

1. HTTP APIs remain in DRF.
2. WebSocket concerns go through Channels routing and consumers.
3. Keep websocket business logic in services, not consumers.

## 7. Team Workflow

1. Implement one bounded context at a time.
2. Add tests with each new service method.
3. Review architecture boundaries before adding cross-app dependencies.

## 8. API Testing

- See `docs/api-testing.md` for the lender-create/borrower-accept-reject workflow.
- Use the collections in `api-collections/`:
	- Postman: `Peer-Lend-Borrow.postman_collection.json`
	- Bruno: `bruno/`
