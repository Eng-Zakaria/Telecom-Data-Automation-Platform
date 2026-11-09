# Telecom lakehouse - common tasks (see README for the full story)
LAB ?= ../azure-local-lab

.PHONY: lab up down run run-stream full dbt test it lint tf-validate checkov dashboard lineage

lab:            ## start shared Azure emulators (Azurite, Event Hubs, Grafana)
	cd $(LAB) && ./scripts/init-env.sh && docker compose --profile streaming up -d

up: lab         ## emulators + Marquez
	docker compose up -d

down:
	docker compose down

run:            ## batch run with 2% injected corruption
	uv run python -m lakehouse --cdr 5000 --chaos 0.02

run-stream:     ## CDRs through Event Hubs, lineage to Marquez
	OPENLINEAGE_URL=http://localhost:5000 uv run python -m lakehouse --cdr 5000 --chaos 0.02 --stream

full:           ## everything: stream, contracts, dbt build + tests, gold publish, lineage
	OPENLINEAGE_URL=http://localhost:5000 uv run python -m lakehouse --cdr 5000 --chaos 0.02 --stream --dbt

dbt:            ## dbt build against the last run's silver tables (set LAKE_PREFIX if you used --prefix)
	cd transform/dbt && uv run --project ../.. dbt build --profiles-dir .

test:           ## unit tests (no containers)
	uv run pytest

it:             ## integration tests against the emulators
	uv run pytest -m integration

lint:
	uv run ruff check lakehouse scripts tests/test_lakehouse_quality.py tests/test_lakehouse_integration.py

tf-validate:
	for e in dev staging prod ephemeral; do (cd infra/environments/$$e && terraform init -backend=false -input=false >/dev/null && terraform validate) || exit 1; done

checkov:
	uvx --from checkov checkov -d infra --config-file infra/.checkov.yml

dashboard:      ## install the Grafana dashboard
	uv run python scripts/grafana_import.py

lineage:        ## assert every gold table traces back to a source
	uv run python scripts/check_lineage.py --marquez http://localhost:5000
