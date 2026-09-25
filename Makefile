SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

COMPOSE := docker compose
APPS_UPSTREAMS := GATEWAY_CORE_UPSTREAM=core-business-service:8080 \
                  GATEWAY_TELEMETRY_UPSTREAM=telemetry-stream-service:8090

.PHONY: help
help: ## List available targets
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z0-9_-]+:.*## / {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.env:
	@cp .env.example .env
	@echo "Created .env from .env.example"

.PHONY: up
up: .env ## Start infrastructure and gateway
	$(COMPOSE) up -d --wait

.PHONY: up-apps
up-apps: .env ## Start infrastructure, gateway, and Go services built from sibling repositories
	$(APPS_UPSTREAMS) $(COMPOSE) --profile apps up -d --build --wait

.PHONY: up-tools
up-tools: .env ## Start infrastructure plus developer tools (Kafka UI on :8085)
	$(COMPOSE) --profile tools up -d --wait

.PHONY: down
down: ## Stop all containers (keeps data)
	$(COMPOSE) --profile apps --profile tools down

.PHONY: reset
reset: ## Stop all containers and delete all data volumes
	$(COMPOSE) --profile apps --profile tools down -v

.PHONY: ps
ps: ## Show container status
	$(COMPOSE) --profile apps --profile tools ps

.PHONY: logs
logs: ## Follow logs (SERVICE=<name> to filter)
	$(COMPOSE) --profile apps --profile tools logs -f $(SERVICE)

.PHONY: topics
topics: ## List Kafka topics
	$(COMPOSE) exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --describe

.PHONY: psql-core
psql-core: ## Open psql on veritrace_core as the owner role
	$(COMPOSE) exec postgres psql -U veritrace_core_owner -d veritrace_core

.PHONY: psql-telemetry
psql-telemetry: ## Open psql on veritrace_telemetry as the owner role
	$(COMPOSE) exec postgres psql -U veritrace_telemetry_owner -d veritrace_telemetry

.PHONY: lint
lint: ## Validate compose file and shell scripts
	$(COMPOSE) config --quiet
	@command -v shellcheck >/dev/null && shellcheck postgres/initdb/*.sh kafka/*.sh mosquitto/config/*.sh || echo "shellcheck not installed; skipped"
