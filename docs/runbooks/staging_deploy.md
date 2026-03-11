# Staging Deployment Runbook

## Overview

This runbook covers two staging deployment paths:
1. **Local Docker staging** — validate the full stack on a developer machine before cloud deployment.
2. **Cloud staging (AWS ECS + RDS)** — long-term target; Terraform config is in `infra/terraform/staging/`.

---

## Prerequisites

| Requirement | Minimum version |
|---|---|
| Docker Desktop | 4.x |
| Docker Compose | v2 |
| Ollama | 0.1.x with `nomic-embed-text` pulled |
| Terraform CLI | 1.5+ (cloud path only) |

Ensure Ollama is running on the host:
```sh
ollama pull nomic-embed-text
ollama serve   # if not already running as a daemon
```

---

## Path 1 — Local Docker Staging

### 1. Configure environment

```sh
cp .env.staging.example .env.staging
# Edit .env.staging — set JWT_SECRET_KEY and confirm PostgreSQL credentials
```

### 2. Build and start the stack

```sh
docker compose -f docker-compose.staging.yml up -d --build
```

The `migrate` service runs `alembic upgrade head` automatically before the `api` service starts.

### 3. Smoke test

```sh
# Health check
curl http://localhost:8001/health

# Authenticated endpoints require a Bearer token
TOKEN=$(python src/app/secrets.py)   # or generate via the auth flow
curl -H "Authorization: Bearer $TOKEN" http://localhost:8001/api/v1/matches
```

### 4. Validate resume ingestion

```sh
# Ingest a resume from Google Drive
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"document_id": "<GDRIVE_DOC_ID>"}' \
  http://localhost:8001/api/v1/resume-ingestion
```

Expected response:
```json
{
  "doc_id": "...",
  "status": "ok",
  "team_member_id": "...",
  "extracted_name": "...",
  "skills_found": 6,
  "experience_months": 48
}
```

### 5. Validate matching with match_percentage

```sh
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "ML Engineer", "description": "...", "required_skills": [...]}' \
  http://localhost:8001/api/v1/jd-skill-mapping
```

Expected fields in each candidate result:
- `match_percentage` (0–100)
- `profile_score` (0.0–1.0)
- `fit_level` (HIGH / MEDIUM / LOW)
- `explanation` including "Overall match: X%" and "Resume semantic similarity: Y%"

### 6. Tear down

```sh
docker compose -f docker-compose.staging.yml down -v
```

---

## Path 2 — Cloud Staging (AWS ECS + RDS)

> **Status**: Terraform configuration is prepared in `infra/terraform/staging/` with commented-out resources. Activate by:
> 1. Creating a VPC or referencing an existing one
> 2. Provisioning an RDS PostgreSQL 15 instance with the pgvector extension
> 3. Building and pushing the Docker image to ECR
> 4. Uncommenting the ECS task definition and service blocks

### Steps

```sh
# 1. Build and push Docker image to ECR
IMAGE_TAG=$(git rev-parse --short HEAD)
aws ecr get-login-password | docker login --username AWS --password-stdin <ECR_URL>
docker build -t ib-job-skill-mapping-system:$IMAGE_TAG .
docker tag ib-job-skill-mapping-system:$IMAGE_TAG <ECR_URL>:$IMAGE_TAG
docker push <ECR_URL>:$IMAGE_TAG

# 2. Apply Terraform (after uncommenting resources)
cd infra/terraform/staging
terraform init
terraform apply \
  -var="image_tag=$IMAGE_TAG" \
  -var="db_username=$DB_USER" \
  -var="db_password=$DB_PASS" \
  -var="ecr_repo_url=<ECR_URL>"

# 3. Run database migrations against RDS
DATABASE_URL="postgresql://$DB_USER:$DB_PASS@<RDS_ENDPOINT>:5432/ib_job_skill_mapping_staging" \
  alembic upgrade head
```

---

## Rollback

**Docker (local)**:
```sh
docker compose -f docker-compose.staging.yml down -v
# Revert code changes, rebuild
docker compose -f docker-compose.staging.yml up -d --build
```

**Cloud (ECS)**:
```sh
# Re-deploy previous image tag
terraform apply -var="image_tag=<PREVIOUS_TAG>" ...
```

---

## Common Issues

| Symptom | Likely cause | Fix |
|---|---|---|
| `api` container exits immediately | DATABASE_URL wrong or DB not ready | Check `migrate` service logs; ensure postgres healthcheck passes |
| `500` on `/api/v1/jd-skill-mapping` | Ollama not reachable | Verify `OLLAMA_BASE_URL` and `ollama serve` is running |
| Empty `match_percentage` | No embeddings in `team_member_embeddings` | Run resume ingestion first |
| Auth `401` | Incorrect Bearer token | Regenerate token via auth endpoint |
