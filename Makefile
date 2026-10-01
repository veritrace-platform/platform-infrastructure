SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

COMPOSE := docker compose
ALL_PROFILES := --profile apps --profile tools --profile tunnel
APPS_UPSTREAMS := GATEWAY_CORE_UPSTREAM=core-business-service:8080 \
                  GATEWAY_TELEMETRY_UPSTREAM=telemetry-stream-service:8090

.PHONY: help
help: ## List available targets
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z0-9_-]+:.*## / {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Creates .env on the first run. Later, when .env.example gains variables, adds them to .env with their
# example values and leaves every existing value alone.
.env: .env.example
	@if [[ ! -f .env ]]; then \
		cp .env.example .env; \
		echo "Created .env from .env.example"; \
	else \
		while IFS= read -r line; do \
			[[ "$$line" =~ ^([A-Z0-9_]+)= ]] || continue; \
			if ! grep -q "^$${BASH_REMATCH[1]}=" .env; then \
				printf '%s\n' "$$line" >> .env; \
				echo "Added $${BASH_REMATCH[1]} to .env"; \
			fi; \
		done < .env.example; \
		touch .env; \
	fi

.PHONY: up
up: .env ## Start infrastructure and gateway
	$(COMPOSE) up -d --wait

.PHONY: up-apps
up-apps: .env ## Start infrastructure, gateway, and Go services built from sibling repositories
	$(APPS_UPSTREAMS) $(COMPOSE) --profile apps up -d --build --wait

.PHONY: up-tools
up-tools: .env ## Start infrastructure plus developer tools (Kafka UI on :8085)
	$(COMPOSE) --profile tools up -d --wait

.PHONY: tunnel
tunnel: ## Public HTTPS URL for phone testing (TUNNEL_TARGET=http://host.docker.internal:3000 for a frontend)
	$(COMPOSE) --profile tunnel run --rm tunnel

.PHONY: down
down: ## Stop all containers (keeps data)
	$(COMPOSE) $(ALL_PROFILES) down

.PHONY: reset
reset: ## Stop all containers and delete all data volumes
	$(COMPOSE) $(ALL_PROFILES) down -v

.PHONY: clean
clean: ## reset + remove locally built service images and dangling build layers
	$(COMPOSE) $(ALL_PROFILES) down -v --rmi local
	docker image prune -f --filter label=com.docker.compose.project=veritrace

.PHONY: disk
disk: ## Show Docker disk usage
	docker system df

.PHONY: ps
ps: ## Show container status
	$(COMPOSE) $(ALL_PROFILES) ps

.PHONY: logs
logs: ## Follow logs (SERVICE=<name> to filter)
	$(COMPOSE) $(ALL_PROFILES) logs -f $(SERVICE)

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
	shellcheck postgres/initdb/*.sh kafka/*.sh mosquitto/config/*.sh
