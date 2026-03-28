SHELL := /bin/bash

.PHONY: demo-check backend-test mcp-test frontend-build frontend-lint

demo-check:
	@echo "Running ConsentOS local readiness checks..."
	@echo "1) Bootstrap .env if missing values"
	python3 scripts/bootstrap_env.py --dry-run || true
	@echo ""
	@echo "2) Start services"
	docker-compose up --build -d
	@echo ""
	@echo "3) Readiness endpoints"
	curl -fsS http://localhost:8000/health/ready
	curl -fsS http://localhost:8100/health/ready
	@echo ""
	@echo "4) Frontend app"
	curl -I -fsS http://localhost:3000 >/dev/null
	@echo "Demo check complete."

backend-test:
	cd backend && python3 -m pytest -q

mcp-test:
	cd mcp && python3 -m pytest -q

frontend-build:
	cd frontend && npm run build

frontend-lint:
	cd frontend && npm run lint
