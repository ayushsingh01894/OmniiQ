.PHONY: help env up down logs migrate backend-setup backend-test backend-lint frontend-setup frontend-test frontend-lint test lint

help:
	@echo "make env            Create .env from .env.example (will not overwrite)"
	@echo "make up             Build and start db, backend, frontend (Docker)"
	@echo "make down           Stop the stack (keeps database volume)"
	@echo "make migrate        Apply Alembic migrations inside the backend container"
	@echo "make backend-setup  Create backend/.venv and install dependencies"
	@echo "make frontend-setup Install frontend dependencies"
	@echo "make test           Run backend and frontend tests"
	@echo "make lint           Run ruff, mypy, eslint, tsc"

env:
	@test -f .env && echo ".env already exists, leaving it alone" || (cp .env.example .env && sed -i.bak "s|^SECRET_KEY=.*|SECRET_KEY=$$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')|" .env && rm -f .env.bak && echo "Created .env with a freshly generated SECRET_KEY")

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f

migrate:
	docker compose exec backend alembic upgrade head

backend-setup:
	cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"

backend-test:
	cd backend && . .venv/bin/activate && pytest

backend-test-pg: ## needs TEST_DATABASE_URL pointing at an empty throw-away PostgreSQL database
	cd backend && . .venv/bin/activate && pytest

backend-lint:
	cd backend && . .venv/bin/activate && ruff check . --exclude .venv && mypy

frontend-setup:
	cd frontend && npm ci

frontend-test:
	cd frontend && npm test

frontend-lint:
	cd frontend && npm run lint && npm run typecheck

test: backend-test frontend-test
lint: backend-lint frontend-lint
