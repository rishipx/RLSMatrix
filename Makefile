PYTHON ?= python

.DEFAULT_GOAL := help
.PHONY: help install format lint typecheck test test-unit check up down build clean

help: ## Show available targets
	@grep -E "^[a-z-]+:.*##" $(MAKEFILE_LIST) | awk -F ":.*## " "{printf \"  %-12s %s\\n\", \$$1, \$$2}"

install: ## Install the project with development dependencies
	$(PYTHON) -m pip install -e ".[dev]"

format: ## Format the code
	ruff format .

lint: ## Check formatting and lint rules
	ruff format --check .
	ruff check .

typecheck: ## Run the static type checker
	mypy

test-unit: ## Run unit tests (no database needed)
	pytest -q -m "not integration"

test: ## Run all tests (integration tests need the sandbox, see CONTRIBUTING.md)
	pytest -q

check: lint typecheck test ## Lint, type-check and test

up: ## Start the application with Docker Compose
	docker compose up --build

down: ## Stop the application and remove the sandbox
	docker compose down --volumes --remove-orphans

build: ## Build the source and wheel distributions
	$(PYTHON) -m build

clean: ## Remove build and cache artifacts
	rm -rf build dist .pytest_cache .ruff_cache .mypy_cache src/*.egg-info
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
