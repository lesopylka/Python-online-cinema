.PHONY: help build up down logs clean init test

help:
	@echo "Online Cinema Management Commands:"
	@echo "  make build     - Build all Docker images"
	@echo "  make up        - Start all services"
	@echo "  make down      - Stop all services"
	@echo "  make logs      - Show logs from all services"
	@echo "  make clean     - Remove all containers, images, and volumes"
	@echo "  make init      - Initialize databases and indexes"
	@echo "  make test      - Run tests"
	@echo "  make monitor   - Start monitoring services only"

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

clean:
	docker-compose down -v --remove-orphans
	docker system prune -a -f

init: up
	@echo "Waiting for services to start..."
	@sleep 30
	docker-compose exec postgres /docker-entrypoint-initdb.d/init-db.sh
	docker-compose exec -T elasticsearch curl -X PUT "http://localhost:9200/_cluster/settings" \
		-H 'Content-Type: application/json' -d '{"persistent": {"cluster.routing.allocation.disk.threshold_enabled": false}}'
	python scripts/create_indexes.py --load-data
	python scripts/load_test_data.py

test:
	docker-compose exec api-gateway python -m pytest /app/tests/ -v

monitor:
	docker-compose up -d prometheus grafana jaeger

status:
	@echo "=== Service Status ==="
	@docker-compose ps
	@echo "\n=== Running Containers ==="
	@docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

restart:
	docker-compose restart

shell-api:
	docker-compose exec api-gateway bash

shell-db:
	docker-compose exec postgres psql -U postgres

update:
	git pull origin main
	docker-compose build
	docker-compose up -d

backup:
	@echo "Creating backup..."
	@mkdir -p backups
	@docker-compose exec postgres pg_dumpall -U postgres > backups/db_backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "Backup created in backups/"

restore:
	@if [ -z "$(file)" ]; then \
		echo "Usage: make restore file=backups/db_backup_YYYYMMDD_HHMMSS.sql"; \
		exit 1; \
	fi
	@echo "Restoring from $(file)..."
	@cat $(file) | docker-compose exec -T postgres psql -U postgres
	@echo "Restore completed"