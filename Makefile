# SPDX-License-Identifier: Apache-2.0
#
#  make              - show this help
#  make dev-image    - build the development Docker image
#  make dev          - drop into a bash shell inside the dev container
#  make test         - run pytest
#  make lint         - ruff check (linter)
#  make format       - ruff format (auto-fix formatting)
#  make format-check - ruff format --check (CI gate, no writes)
#  make typecheck    - mypy
#  make check        - lint + format-check + typecheck + test  (full CI gate)
#  make clean        - remove caches and build artifacts
#
# Requirements (local workflow):
#   uv  (https://docs.astral.sh/uv/)
#
# Requirements (Docker workflow):
#   docker

PYTHON_VERSION ?= 3.11
PROJECT        := ccsds-data-messages
IMAGE          := $(PROJECT):dev
DEV_USERNAME   := $(shell whoami)

.DEFAULT_GOAL := help

.PHONY: help dev-image dev test lint format format-check typecheck check clean

help: ## Show this help message
	@awk 'BEGIN { FS = "[ \t]+##[ \t]*" } /^[a-zA-Z_-]+:.*##/ { \
	    printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2 \
	}' $(MAKEFILE_LIST)

dev-image: ## Build the development Docker image
	docker build \
	    --target=dev \
	    --build-arg USER_UID=$(shell id -u) \
	    --build-arg USER_GID=$(shell id -g) \
	    --build-arg DEV_USERNAME=$(DEV_USERNAME) \
	    --build-arg PYTHON_VERSION=$(PYTHON_VERSION) \
	    --tag=$(IMAGE) \
	    .

dev: dev-image ## Drop into a bash shell inside the dev container (source mounted live)
	docker run \
	    --name=$(PROJECT)-dev \
	    --interactive \
	    --tty \
	    --rm \
	    --volume="$(CURDIR):/workspace" \
	    --volume="$(HOME)/.gitconfig:/home/$(DEV_USERNAME)/.gitconfig:ro" \
	    --volume="$(HOME)/.ssh:/home/$(DEV_USERNAME)/.ssh:ro" \
	    $(IMAGE) \
	    /bin/bash

test: ## Run tests with pytest
	uv run pytest

lint: ## Lint with ruff
	uv run ruff check .

format: ## Format with ruff (applies changes)
	uv run ruff format .

format-check: ## Check formatting without applying changes
	uv run ruff format --check .

typecheck: ## Type-check with mypy
	uv run mypy -p ccsds_data_messages

pylint: ## Lint with pylint
	uv run pylint ccsds_data_messages

check: lint format-check typecheck pylint test ## Run all checks - lint, format, typecheck, pylint, tests

clean: ## Remove caches and build artifacts
	rm -rf .ruff_cache .mypy_cache .pytest_cache dist/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
