# Telecom Platform - Makefile for local development

.PHONY: up down logs status init validate apply destroy

# Local dev stack
up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

status:
	docker-compose ps

restart:
	docker-compose restart

# Terraform
tf-init:
	cd infra && terraform init

tf-plan:
	cd infra/environments/dev && terraform plan -var-file="dev.tfvars"

tf-apply:
	cd infra/environments/dev && terraform apply -var-file="dev.tfvars" -auto-approve

tf-destroy:
	cd infra/environments/dev && terraform destroy -var-file="dev.tfvars" -auto-approve

# Documentation
docs:
	python -m mkdocs serve

# Testing
test:
	pytest tests/

# Code quality
lint:
	black --check .
	isort --check .
	flake8 .

format:
	black .
	isort .

# CI/CD
ci: lint test tf-validate

tf-validate:
	cd infra && terraform fmt -check && terraform validate
