.PHONY: up down logs test lint fmt migrate

up:
	docker compose up --build

down:
	docker compose down -v

logs:
	docker compose logs -f

test:
	docker compose up -d postgres redis
	cd backend && uv run pytest

lint:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app
	cd web && npm run lint

fmt:
	cd backend && uv run ruff format .
	cd web && npm run format

migrate:
	cd backend && uv run alembic upgrade head
