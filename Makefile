.PHONY: help install test lint format build deploy-dev deploy-staging deploy-prod clean

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install dependencies
	uv sync --extra dev

test: ## Run tests
	uv run pytest

lint: ## Run linting
	uv run black --check .
	uv run isort --check-only .
	uv run mypy src/

format: ## Format code
	uv run black .
	uv run isort .

build: ## Build Lambda package
	./scripts/build.sh

deploy-dev: ## Deploy to development environment
	./scripts/deploy.sh dev

deploy-staging: ## Deploy to staging environment
	./scripts/deploy.sh staging

deploy-prod: ## Deploy to production environment
	./scripts/deploy.sh prod

terraform-init: ## Initialize Terraform
	cd terraform && terraform init

terraform-plan-dev: ## Plan Terraform changes for dev
	cd terraform && terraform plan -var-file="environments/dev.tfvars"

terraform-plan-prod: ## Plan Terraform changes for prod
	cd terraform && terraform plan -var-file="environments/prod.tfvars"

clean: ## Clean build artifacts
	rm -rf deployment/package/
	rm -rf deployment/layer*/
	rm -rf deployment/function/
	rm -f deployment/lambda-package.zip
	rm -f deployment/lambda-layer*.zip
	rm -f deployment/lambda-function.zip
	rm -f deployment/requirements*.txt