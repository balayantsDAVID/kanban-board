DEV = -f docker-compose.yml -f docker-compose.dev.yml
TEST_DB = postgresql+asyncpg://app:app@localhost:5433/app_test

.PHONY: up up-prod down clean logs test lint fmt migrate

up:
	docker compose $(DEV) up --build

up-prod:
	docker compose up --build -d

down:
	docker compose down

clean:
	docker compose down -v

logs:
	docker compose logs -f

test:
	docker compose $(DEV) up -d --wait postgres redis
	docker compose exec -T postgres psql -U app -d postgres -c "CREATE DATABASE app_test" || true
	cd backend && DATABASE_URL=$(TEST_DB) uv run alembic upgrade head
	cd backend && uv run pytest

lint:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app
	cd web && npm run lint

fmt:
	cd backend && uv run ruff format .
	cd web && npm run format

migrate:
	cd backend && uv run alembic upgrade head
