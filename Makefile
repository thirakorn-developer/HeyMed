.PHONY: dev db db-down migrate seed test lint

db:
	docker compose up -d db

db-down:
	docker compose down

dev: db
	cd backend && uvicorn app.main:app --reload --port 8000

migrate:
	cd backend && alembic upgrade head

migration:
	cd backend && alembic revision --autogenerate -m "$(msg)"

seed:
	cd backend && python -m scripts.seed_rxnorm

test:
	cd backend && pytest -v

lint:
	cd backend && ruff check . && ruff format --check .

format:
	cd backend && ruff check --fix . && ruff format .
