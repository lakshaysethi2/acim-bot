# ACIM Bot — Docker Compose shortcuts
#
# Usage:
#   make build        Build the Docker image
#   make up           Start the bot in the background
#   make down         Stop and remove the container
#   make logs         Tail container logs
#   make restart      Restart the container
#   make health       Show container health status
#   make shell        Open a shell inside the running container
#   make clean        Remove containers, images, and volumes

COMPOSE = docker compose

.PHONY: build up down logs restart health shell clean

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

restart:
	$(COMPOSE) restart

health:
	@docker inspect --format='{{.State.Health.Status}}' acim-bot 2>/dev/null || echo "Container not running"

shell:
	docker exec -it acim-bot /bin/bash

clean:
	$(COMPOSE) down --rmi all --volumes --remove-orphans
