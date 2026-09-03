# Runbook

## Pipeline Failure Recovery

### Symptom: Ingestion pipeline failed
**Check**:
```bash
# Check pipeline status
az datafactory pipeline-run list --resource-group rg-telecom-dev --factory-name adf-telecom-dev

# Check error details
az datafactory pipeline-run get --resource-group rg-telecom-dev --factory-name adf-telecom-dev --pipeline-run-id <run-id>
```

**Recovery**:
1. Fix upstream data source issue
2. Rerun pipeline with backfill
3. Verify data quality

### Symptom: Schema drift detected
**Check**:
```bash
# Check Great Expectations results
cd quality && python check_schema_drift.py

# View failing expectations
grep -r "expectation_result" quality/results/
```

**Recovery**:
1. Update dbt model to match new schema
2. Re-run transformation
3. Update data dictionary

### Symptom: ML model drift
**Check**:
```bash
# Check MLflow metrics
mlflow ui --port 5000

# Compare current vs baseline
mlflow search-experiments --filter "tags.environment='prod'"
```

**Recovery**:
1. Trigger retraining (drift detection)
2. Validate new model
3. Champion/challenger evaluation
4. Promote if metrics improve

## Secret Rotation

### Step-by-step
1. Generate new secret in Key Vault
2. Update access policies if needed
3. Restart affected services
4. Verify connectivity
5. Delete old secret after 24h

### Commands
```bash
# Create new secret
az keyvault secret set --vault-name kv-telecom-dev --name <secret-name> --value <new-value>

# Verify access
az keyvault secret show --vault-name kv-telecom-dev --name <secret-name>
```

## Environment Provisioning

### Dev Environment
```bash
cd infra/environments/dev
terraform init
terraform plan -var-file="dev.tfvars"
terraform apply -var-file="dev.tfvars"
```

### Ephemeral Environment (PR)
```bash
# Triggered automatically by GitHub Actions
# Clean up on PR close
cd infra/environments/ephemeral
terraform destroy -var="branch_name=feature-xxx"
```

## On-Call Escalation

### Level 1: Automated Response
- Pipeline failures: Auto-retry (3 attempts)
- Data quality: Quarantine to dead-letter
- ML drift: Trigger retraining

### Level 2: Manual Intervention
- If auto-retry fails: Investigate upstream
- If dead-letter needs review: Manual validation
- If retraining fails: Model rollback

### Level 3: Team Escalation
- Infrastructure issues: Contact cloud team
- Business logic issues: Contact domain team
- Urgent production issues: Page senior engineer

## Health Checks

### Daily
```bash
# Check all services
docker-compose ps

# Verify Azure resources
az resource list --resource-group rg-telecom-dev --query "[].name"

# Check pipeline runs
az datafactory pipeline-run list --resource-group rg-telecom-dev
```

### Weekly
```bash
# Storage growth
az storage account show-statistics --account-name sttelecomdev001

# Cost estimation
az monitor metrics list --resource /subscriptions/<id>/resourceGroups/rg-telecom-dev
```

## Contacts

| Role | Escalation |
|------|-----------|
| Data Engineer | Level 1 |
| Platform Engineer | Level 2 |
| Cloud Architect | Level 3 |
| Product Owner | Business decisions |
