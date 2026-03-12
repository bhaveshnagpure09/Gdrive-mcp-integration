# IB Job Skill Mapping System

An AI-powered intelligent job requisition and skill mapping system that matches job descriptions with team member skills and evaluates candidate availability using LangGraph-based multi-agent orchestration.

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [API Documentation](#api-documentation)
- [Resume Ingestion via Google Drive (MCP)](#resume-ingestion-via-google-drive-mcp)
- [Testing](#testing)
- [Performance Testing](#performance-testing)
- [Project Structure](#project-structure)
- [Development Phases](#development-phases)
- [Contributing](#contributing)

## ⚡ Quick Start

Get the system up and running in 5 minutes:

### Step 1: Clone and Setup Environment

```bash
# Clone repository
git clone https://github.com/aaryaa-infobeans/ib-job-skill-mapping-system.git
cd ib-job-skill-mapping-system

# Create and activate virtual environment
python -m venv venv

# Windows PowerShell
.\venv\Scripts\Activate.ps1

# macOS/Linux
source venv/bin/activate

# Install dependencies
pip install -e ".[dev]"
```

### Step 2: Start Database

```bash
# Start PostgreSQL using Docker Compose
docker compose up -d postgres

# Wait for database to be ready (about 10 seconds)
```

### Step 3: Configure Environment

Create a `.env` file in the project root:

```bash
# Required: Database connection
DATABASE_URL=postgresql://user:password@localhost:5432/ib_job_skill_mapping

# Required: OpenAI API key (get from https://platform.openai.com/api-keys)
OPENAI_API_KEY=sk-your-openai-api-key-here

# Optional: JWT secret (generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
SECRET_KEY=your-generated-secret-key-here
```

### Step 4: Run Database Migrations

```bash
# Create database schema
alembic upgrade head
```

### Step 5: Start the Application

```bash
# Start API server with hot-reload
uvicorn src.main:app --reload
```

The API is now running at:
- **Swagger UI**: http://localhost:8000/docs
- **API Base**: http://localhost:8000
- **Health Check**: http://localhost:8000/health

### Step 6: Test the API

```bash
# Check health endpoint
curl http://localhost:8000/health

# Expected output:
# {"status":"healthy","timestamp":"2026-02-03T...","database":"connected"}
```

### Next Steps

- **Configure OAuth Client**: See [OAuth Client Setup](#oauth-client-setup) section
- **Load Sample Data**: Run `psql -U user -h localhost -d ib_job_skill_mapping -f specs-data/ib-job-skill-mapping-system.sql`
- **Run Tests**: Execute `pytest` to verify installation
- **Explore API**: Visit http://localhost:8000/docs for interactive API documentation

---

## ✨ Features

### Core Functionality
- **Job Description Parsing** - AI-powered extraction of skills, experience, and requirements from JD text
- **Skill Normalization** - Standardizes skill terminology using LLM-based semantic analysis
- **Intelligent Matching** - Scores team members against requisitions based on skills, experience, and availability
- **Availability Evaluation** - Calculates capacity based on project allocations and timelines
- **Result Aggregation** - Ranks and organizes matching results with detailed explanations
- **Resume Ingestion (MCP)** - Ingest resumes from Google Drive (PDF, DOCX, Google Docs) via the MCP pipeline; auto-creates profile embeddings and team member records

### Technical Features
- **Multi-Agent AI System** - LangGraph orchestration with 6 specialized agents
- **RESTful API** - FastAPI-based async endpoints with OpenAPI documentation
- **OAuth2 Security** - JWT-based authentication with scope-based authorization
- **Bulk Operations** - Idempotent bulk upsert for team member skill availability
- **Audit Trail** - Comprehensive logging of all operations with metadata
- **Performance Optimized** - P95 latency < 2s, handles 100+ concurrent requests
- **Scalable Architecture** - Tested with 5x production data volume

## 🏗️ Architecture

### High-Level Architecture

```
┌─────────────┐     ┌──────────────────────────────────────┐     ┌──────────────┐
│   Client    │────▶│         FastAPI Layer                │────▶│  PostgreSQL  │
│ Application │     │  (FR-1, FR-2, FR-3 Endpoints)        │     │   Database   │
└─────────────┘     └──────────────────────────────────────┘     └──────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │   LangGraph Multi-Agent AI    │
                    │         Orchestrator          │
                    └───────────────────────────────┘
                                    │
            ┌───────────────────────┼───────────────────────┐
            ▼                       ▼                       ▼
    ┌───────────────┐      ┌────────────────┐     ┌──────────────┐
    │ JD Parsing    │      │ Skill Normal.  │     │  Matching &  │
    │    Agent      │      │     Agent      │     │Score Agent   │
    └───────────────┘      └────────────────┘     └──────────────┘
            │                       │                       │
            └───────────────────────┼───────────────────────┘
                                    ▼
                    ┌───────────────────────────────┐
                    │   Availability Evaluation     │
                    │   + Result Aggregation        │
                    └───────────────────────────────┘
```

### LangGraph Agent Topology

```
START → JD Parsing → Skill Normalization → Matching & Scoring
                                                    │
                                                    ▼
                                          Availability Evaluation
                                                    │
                                                    ▼
                                           Result Aggregation → END
```

## 📦 Prerequisites

### Required Software

- **Python 3.11+** - Core runtime
- **PostgreSQL 15+** - Database
- **Docker & Docker Compose** - Container orchestration (recommended)
- **Git** - Version control

### Optional Tools

- **k6** - Performance testing (Phase 6)
- **HTTPie or curl** - API testing
- **pgAdmin** - Database management UI

### API Keys

- **OpenAI API Key** - Required for LLM-based agents
  - Get from: https://platform.openai.com/api-keys
  - Set in `.env` file as `OPENAI_API_KEY`

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/aaryaa-infobeans/ib-job-skill-mapping-system.git
cd ib-job-skill-mapping-system
```

### 2. Set Up Python Environment

#### Using venv (Recommended)

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Windows (CMD)
.\venv\Scripts\activate.bat

# macOS/Linux
source venv/bin/activate

# Install dependencies
pip install -e ".[dev]"
```

#### Using conda

```bash
conda create -n ib-job-skill python=3.11
conda activate ib-job-skill
pip install -e ".[dev]"
```

### 3. Start PostgreSQL Database

#### Using Docker Compose (Recommended)

```bash
docker compose up -d postgres
```

This starts PostgreSQL on `localhost:5432` with:
- **Database**: `ib_job_skill_mapping`
- **User**: `user`
- **Password**: `password`

#### Using Local PostgreSQL

If you have PostgreSQL installed locally, create the database:

```bash
psql -U postgres
CREATE DATABASE ib_job_skill_mapping;
CREATE USER user WITH PASSWORD 'password';
GRANT ALL PRIVILEGES ON DATABASE ib_job_skill_mapping TO user;
\q
```

### 4. Run Database Migrations

```bash
alembic upgrade head
```

This creates all required tables:
- `team_members`
- `team_member_allocations`
- `requisition_requests`
- `requisition_parsed_skills`
- `requisition_matches`
- `oauth_clients`
- `audit_log`

### 5. Load Sample Data (Optional)

```bash
# Load initial schema with sample OAuth client
psql -U user -h localhost -d ib_job_skill_mapping -f specs-data/ib-job-skill-mapping-system.sql
```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/ib_job_skill_mapping

# OpenAI API Configuration
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL=gpt-4-turbo-preview

# Application Configuration
APP_ENV=development
LOG_LEVEL=INFO

# Security Configuration
SECRET_KEY=your-secret-key-for-jwt-signing-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Server Configuration
HOST=0.0.0.0
PORT=8000
RELOAD=true
```

### Generate Secret Key

```bash
# Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# OpenSSL
openssl rand -base64 32
```

### OAuth Client Setup

Register an OAuth client in the database:

```bash
# Connect to database
psql -U user -h localhost -d ib_job_skill_mapping

# Create OAuth client
INSERT INTO oauth_clients (client_id, client_name, hashed_secret, scopes, is_active)
VALUES (
    'test-client',
    'Test Application',
    crypt('test-secret', gen_salt('bf')),
    ARRAY['read', 'write'],
    true
);

# Exit psql
\q
```

**Generate JWT Token for Testing:**

```bash
# Using Python
python -c "from jose import jwt; from datetime import datetime, timedelta; print(jwt.encode({'sub': 'test-client', 'scopes': ['read', 'write'], 'exp': datetime.utcnow() + timedelta(hours=24)}, 'your-secret-key-here', algorithm='HS256'))"
```

Use this token in API requests:
```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" http://localhost:8000/api/v1/jd-skill-mapping/
```

## 🏃 Running the Application

### Development Mode

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Or using the convenience script:

```bash
# Windows PowerShell
python -m uvicorn src.main:app --reload

# macOS/Linux
python3 -m uvicorn src.main:app --reload
```

The API will be available at:
- **API Base**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### Production Mode

```bash
# Using Gunicorn with Uvicorn workers (Linux/macOS)
gunicorn src.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -

# Windows (use Uvicorn directly)
uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Using Docker

```bash
# Build image
docker build -t ib-job-skill-mapping:latest .

# Run container
docker run -d \
  -p 8000:8000 \
  --env-file .env \
  --name ib-job-skill-api \
  ib-job-skill-mapping:latest
```

### Health Check

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2026-02-03T10:30:00Z",
  "database": "connected"
}
```

## 📚 API Documentation

### Authentication

All API endpoints require OAuth2 Bearer token authentication:

```bash
# Get access token (pseudo-code, implement OAuth2 flow)
curl -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=test-client&client_secret=test-secret&grant_type=client_credentials"
```

### Core Endpoints

#### FR-1: Submit Job Requisition

```bash
POST /api/v1/jd-skill-mapping/
Authorization: Bearer <token>
Content-Type: application/json

{
  "request_id": "REQ-2026-001",
  "title": "Senior Backend Engineer",
  "role": "Backend Development",
  "priority": "HIGH",
  "location": ["Bangalore", "Remote"],
  "work_mode": ["Remote", "Hybrid"],
  "jd_text": "We are seeking a Senior Backend Engineer with 5+ years experience in Python, FastAPI, PostgreSQL..."
}
```

#### FR-2: Get Matching Results

```bash
GET /api/v1/jd-skill-mapping/{correlation_id}/matches
Authorization: Bearer <token>
```

#### FR-3: Bulk Upsert Team Member Skills

```bash
POST /api/v1/team-members/skill-availability/bulk-upsert
Authorization: Bearer <token>
Content-Type: application/json

{
  "team_members": [
    {
      "team_member_id": "TM001",
      "name": "John Doe",
      "email": "john.doe@example.com",
      "designation": "Senior Engineer",
      "primary_skills": ["Python", "FastAPI", "PostgreSQL"],
      "secondary_skills": ["Docker", "Kubernetes"],
      "total_experience_years": 8,
      "relevant_experience_years": 5
    }
  ]
}
```

### Monitoring Endpoints

```bash
# Prometheus metrics
GET /api/v1/metrics

# Audit logs
GET /api/v1/audit/logs?entity_type=requisition&limit=100
```

For detailed API documentation, visit http://localhost:8000/docs after starting the server.

## 📄 Resume Ingestion via Google Drive (MCP)

The system can ingest team-member resumes directly from **Google Drive** through the MCP (Model Context Protocol) ingestion pipeline. Uploaded resumes are converted to structured profile embeddings that power the AI matching engine.

### How the Pipeline Works

```
Google Drive (PDF / DOCX / Google Doc)
         │
         ▼  GoogleDriveMCPClient.fetch_resume()
   Raw resume text
         │
         ▼  PIIScrubber → ResumeParser
   Scrubbed profile text  +  parsed fields
   (name, designation, skills, experience)
         │
         ▼  EmbeddingGenerator.generate()
   1536-dim vector embedding
         │
         ▼  EmbeddingRepository.upsert()
   team_member_embeddings  (PostgreSQL / pgvector)
         │
         ▼  Auto-create / update team_member row
   team_member  (full_name synced from parsed resume)
```

> **Idempotency**: Re-ingesting the same file is a no-op when `modifiedTime` hasn't changed. Only updated files trigger a full re-process.

---

### Prerequisites

| Component | Purpose |
|-----------|---------|
| Google Cloud project with Drive API enabled | Access resumes |
| OAuth2 credentials JSON | Authenticate the MCP client |
| `credentials.json` placed in the project root | Loaded by the API at startup |

#### Get OAuth2 Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → **APIs & Services → Credentials**.
2. Create an **OAuth 2.0 Client ID** (Desktop app type).
3. Enable the **Google Drive API** for the project.
4. Download the credentials file and save it as `credentials.json` in the project root.
5. Set the path via environment variable if using a non-default location:
   ```bash
   GDRIVE_CREDENTIALS_PATH=/path/to/your/credentials.json
   ```

---

### Supported Resume Formats

| Format | MIME Type |
|--------|-----------|
| Google Docs | `application/vnd.google-apps.document` |
| PDF | `application/pdf` |
| DOCX | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |
| DOC (legacy) | `application/msword` |

Extra Python dependencies required for binary formats:

```bash
pip install pypdf python-docx
```

---

### Ingest a Single Resume

```bash
POST /api/v1/ingest-resume
Authorization: Bearer <token>
Content-Type: application/json

{
  "storage": "gdrive",
  "doc_id": "1T1ApvOdTGRqX4KUa6-8UnXkzZHFofz-Q"
}
```

You can pass either the bare Drive document ID **or** the full Google Docs / Drive URL — it is stripped automatically:

```json
{
  "storage": "gdrive",
  "doc_id": "https://docs.google.com/document/d/1T1ApvOdTGRqX4KUa6-8UnXkzZHFofz-Q/edit"
}
```

To pin a resume to a specific team member ID rather than letting the system extract it:

```json
{
  "storage": "gdrive",
  "doc_id": "1T1ApvOdTGRqX4KUa6-8UnXkzZHFofz-Q",
  "team_member_id": "bhavesh_nagpure"
}
```

#### Response

```json
{
  "ingested": 1,
  "skipped": 0,
  "failed": 0,
  "details": [
    {
      "doc_id": "1T1ApvOdTGRqX4KUa6-8UnXkzZHFofz-Q",
      "file_name": "1T1ApvOdTGRqX4KUa6-8UnXkzZHFofz-Q",
      "status": "ok",
      "team_member_id": "bhavesh_nagpure",
      "extracted_name": "Bhavesh Nagpure",
      "skills_found": 12,
      "experience_months": 42
    }
  ]
}
```

Possible `status` values per detail entry:

| Status | Meaning |
|--------|---------|
| `ok` | Successfully ingested for the first time |
| `updated` | File has changed since last ingestion — re-ingested |
| `already_ingested` | File unchanged (`modifiedTime` match) — skipped |
| `failed` | Ingestion error; check `reason` field |

---

### Batch-Ingest an Entire Drive Folder

```bash
POST /api/v1/ingest-resume
Authorization: Bearer <token>
Content-Type: application/json

{
  "storage": "gdrive",
  "fetch_all": true,
  "folder_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs"
}
```

Omit `folder_id` to sweep the entire Google Drive:

```json
{
  "storage": "gdrive",
  "fetch_all": true
}
```

The full URL of a folder also works:

```json
{
  "storage": "gdrive",
  "fetch_all": true,
  "folder_id": "https://drive.google.com/drive/folders/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs"
}
```

#### Batch Response

```json
{
  "ingested": 45,
  "skipped": 3,
  "failed": 0,
  "details": [
    { "doc_id": "...", "status": "ok",               "extracted_name": "Alice Kumar",   "skills_found": 8  },
    { "doc_id": "...", "status": "already_ingested",  "extracted_name": "Bob Sharma",    "skills_found": 11 },
    { "doc_id": "...", "status": "updated",           "extracted_name": "Charlie Singh", "skills_found": 6  }
  ]
}
```

---

### Using PowerShell (staging environment)

```powershell
$token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0LXVzZXIiLCJleHAiOjk5OTk5OTk5OTl9.7gDJtxuziSq8wDaUVIuBuO6XmBe3AaMUP-z2GM7YfuQ"
$headers = @{ Authorization = "Bearer $token"; "Content-Type" = "application/json" }

# Single resume
$body = '{"storage":"gdrive","doc_id":"1T1ApvOdTGRqX4KUa6-8UnXkzZHFofz-Q"}'
Invoke-RestMethod "http://localhost:8001/api/v1/ingest-resume" -Method Post -Headers $headers -Body $body

# Batch ingest from a folder
$body = '{"storage":"gdrive","fetch_all":true,"folder_id":"1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs"}'
Invoke-RestMethod "http://localhost:8001/api/v1/ingest-resume" -Method Post -Headers $headers -Body $body
```

---

### What Gets Stored

After ingestion the following database rows are created or updated:

| Table | What is stored |
|-------|---------------|
| `team_member` | Auto-created if not present (designation, experience_months). `full_name` populated from resume. |
| `team_member_embeddings` | `profile_text` (scrubbed full-text), 1536-dim `embedding` vector, `metadata_json` (name, designation, skills list, experience, source doc ID, Drive `modifiedTime`) |

The `metadata_json` structure stored per embedding:

```json
{
  "source_doc_id": "1T1ApvOdTGRqX4KUa6-8UnXkzZHFofz-Q",
  "modified_time": "2026-01-15T09:22:11.000Z",
  "extracted_name": "Bhavesh Nagpure",
  "designation": "Senior Software Engineer",
  "experience_months": 42,
  "skills": ["Python", "RAG", "LangChain", "Machine Learning", "FastAPI"],
  "team_member_id_source": "extracted",
  "storage_source": "gdrive"
}
```

---

### Troubleshooting

#### `503 Google Drive authentication failed`

- Verify `credentials.json` exists at the path pointed to by `GDRIVE_CREDENTIALS_PATH` (default: project root).
- Ensure the credentials are for a **Desktop** OAuth2 client and the Drive API is enabled.
- Re-run the OAuth2 consent flow to refresh expired tokens.

#### `502 Bad Gateway` on batch ingest

- The Drive API rate limit may have been hit. Wait a few seconds and retry.
- Check that the `folder_id` is accessible to the authenticated account.

#### `status: "failed"` with `reason: "Embedding error: ..."`

- The `OPENAI_API_KEY` is missing or invalid. Verify it in `.env`.

#### `status: "already_ingested"` for a file you just updated

- The Drive `modifiedTime` must change for a re-ingest to trigger. Make and save any edit to the Google Doc.

#### Extracted name is empty / skills list looks wrong

- The resume parser uses heuristic extraction. Ensure the resume follows a standard format with clear sections (e.g. **Skills**, **Experience**).
- Skills listed as `Python (3.5, 5)` may be split incorrectly due to the comma in the rating notation. Consider using a plain list format instead.

---

## 🧪 Testing

### Unit and Integration Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_api.py

# Run specific test
pytest tests/test_api.py::test_create_requisition

# Verbose output
pytest -v

# Stop on first failure
pytest -x
```

### Test Coverage

```bash
# Generate coverage report
pytest --cov=src --cov-report=term-missing

# View HTML report
pytest --cov=src --cov-report=html
open htmlcov/index.html  # macOS
start htmlcov/index.html  # Windows
```

### Code Quality

```bash
# Format code with Black
black src/ tests/

# Check formatting without changes
black --check src/ tests/

# Lint with Ruff
ruff check src/ tests/

# Auto-fix linting issues
ruff check --fix src/ tests/

# Type checking with mypy (if configured)
mypy src/
```

## 🚀 Performance Testing

Phase 6 includes comprehensive performance testing with k6.

### Install k6

```bash
# macOS
brew install k6

# Windows
choco install k6

# Linux
sudo apt-get install k6
```

### Run Performance Tests

```bash
# Set authentication token
export AUTH_TOKEN="your-jwt-token"

# Smoke test (30 seconds, 1 user)
k6 run performance-tests/smoke-test.js

# Load test (6 minutes, 10→100 users)
k6 run performance-tests/load-test.js

# Stress test (30 minutes, 100→400 users)
k6 run performance-tests/stress-test.js

# Generate HTML report
k6 run --out json=results.json performance-tests/load-test.js
```

### Performance Targets

| Metric | Target | Test Coverage |
|--------|--------|---------------|
| P95 Latency | < 2 seconds | ✅ Load test |
| P99 Latency | < 5 seconds | ✅ Load test |
| Throughput | ≥ 100 req/s | ✅ Load test |
| Error Rate | < 1% | ✅ All tests |
| Scalability | 5x production | ✅ Data generation |

See [docs/phase-6-testing-guide.md](docs/phase-6-testing-guide.md) for detailed testing procedures.

### Scalability Testing

```bash
# Generate 5x production data
python scripts/generate_test_data.py --scale 5 --output test_data_5x.sql

# Load to database
psql -U user -h localhost -d ib_job_skill_mapping -f test_data_5x.sql

# Cleanup test data
python scripts/cleanup_test_data.py \
  --database postgresql://user:password@localhost:5432/ib_job_skill_mapping \
  --metadata scale_test
```

### Idempotency Testing

```bash
# Test retry behavior
python tests/test_idempotent_retry.py --auth-token "your-jwt-token"
```

## � Troubleshooting

### Common Setup Issues

#### Issue: `psycopg2` installation fails

**Solution:**
```bash
# Windows: Install Visual C++ Build Tools first
# Or use binary package
pip install psycopg2-binary
```

#### Issue: Docker Compose not found

**Solution:**
```bash
# Check Docker installation
docker --version
docker compose version

# If using older Docker, try:
docker-compose up -d postgres
```

#### Issue: Port 5432 already in use

**Solution:**
```bash
# Check what's using port 5432
# Windows PowerShell
netstat -ano | findstr :5432

# Kill the process or use different port in docker-compose.yml
ports:
  - "5433:5432"  # Changed host port to 5433

# Update DATABASE_URL accordingly
DATABASE_URL=postgresql://user:password@localhost:5433/ib_job_skill_mapping
```

#### Issue: Alembic migration fails

**Solution:**
```bash
# Check database connection
psql -U user -h localhost -d ib_job_skill_mapping -c "SELECT 1"

# Reset database if needed
alembic downgrade base
alembic upgrade head

# Or recreate database
psql -U user -h localhost -c "DROP DATABASE IF EXISTS ib_job_skill_mapping"
psql -U user -h localhost -c "CREATE DATABASE ib_job_skill_mapping"
alembic upgrade head
```

#### Issue: OpenAI API key not working

**Solution:**
```bash
# Verify .env file is in project root
ls -la .env  # macOS/Linux
dir .env     # Windows

# Test API key
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer YOUR_OPENAI_API_KEY"

# Make sure .env is loaded (restart uvicorn after changing .env)
```

#### Issue: `uvicorn: command not found`

**Solution:**
```bash
# Ensure virtual environment is activated
# You should see (venv) in your prompt

# Windows PowerShell
.\venv\Scripts\Activate.ps1

# macOS/Linux
source venv/bin/activate

# Verify installation
pip list | grep uvicorn

# If not installed
pip install -e ".[dev]"
```

#### Issue: Module import errors

**Solution:**
```bash
# Install package in editable mode
pip install -e ".[dev]"

# Verify src is in Python path
python -c "import sys; print('\n'.join(sys.path))"

# Run from project root directory
cd /path/to/ib-job-skill-mapping-system
uvicorn src.main:app --reload
```

#### Issue: Tests failing

**Solution:**
```bash
# Ensure test database is set up
export DATABASE_URL=postgresql://user:password@localhost:5432/ib_job_skill_mapping_test
alembic upgrade head

# Clear pytest cache
pytest --cache-clear

# Run with verbose output
pytest -v

# Run specific test
pytest tests/test_api.py -v
```

### Performance Issues

#### Slow API response times

**Causes & Solutions:**

1. **Database connection pool exhausted**
   ```bash
   # Increase pool size in src/config.py
   SQLALCHEMY_POOL_SIZE = 20
   SQLALCHEMY_MAX_OVERFLOW = 40
   ```

2. **Missing database indexes**
   ```sql
   -- Add indexes for frequently queried columns
   CREATE INDEX CONCURRENTLY idx_team_members_skills 
   ON team_members USING GIN(primary_skills);
   
   CREATE INDEX CONCURRENTLY idx_requisitions_status 
   ON requisition_requests(status);
   ```

3. **OpenAI API timeout**
   ```bash
   # Increase timeout in agent configuration
   # Check network connectivity to api.openai.com
   ```

### Getting Help

If you encounter issues not covered here:

1. **Check logs**: Look at application logs for detailed error messages
2. **Review specs**: Check [specs/](specs/) directory for requirements
3. **GitHub Issues**: Search existing issues or create a new one
4. **Documentation**: Review [docs/phase-6-testing-guide.md](docs/phase-6-testing-guide.md)



```
ib-job-skill-mapping-system/
├── src/                          # Source code
│   ├── main.py                   # FastAPI application entry point
│   ├── api/                      # API routes (FR-1, FR-2, FR-3)
│   ├── models/                   # SQLAlchemy models
│   ├── schemas/                  # Pydantic schemas
│   ├── agents/                   # LangGraph AI agents
│   ├── services/                 # Business logic
│   ├── auth/                     # OAuth2 authentication
│   └── config.py                 # Configuration management
├── tests/                        # Test suites
│   ├── test_api.py              # API endpoint tests
│   ├── test_agents.py           # Agent unit tests
│   └── test_idempotent_retry.py # Idempotency tests
├── performance-tests/            # k6 load tests
│   ├── smoke-test.js            # Quick validation
│   ├── load-test.js             # Realistic load
│   ├── stress-test.js           # Breaking point
│   └── README.md                # Testing guide
├── scripts/                      # Utility scripts
│   ├── generate_test_data.py    # Test data generation
│   └── cleanup_test_data.py     # Data cleanup
├── alembic/                      # Database migrations
│   ├── versions/                # Migration files
│   └── env.py                   # Alembic configuration
├── docs/                         # Documentation
│   ├── phase-6-testing-guide.md # Performance testing guide
│   └── architecture.md          # Architecture documentation
├── specs/                        # Requirements & specifications
│   ├── plan.md                  # Implementation plan
│   ├── tasks.md                 # Phase-wise tasks
│   ├── ai/                      # AI agent specifications
│   ├── data/                    # Data model specifications
│   ├── functional/              # Functional requirements
│   └── non-functional/          # Non-functional requirements
├── specs-data/                   # Sample data & schemas
│   └── ib-job-skill-mapping-system.sql
├── docker-compose.yml           # Docker Compose configuration
├── pyproject.toml               # Python project configuration
├── alembic.ini                  # Alembic configuration
├── .env                         # Environment variables (create this)
└── README.md                    # This file
```

## 🏗️ Development Phases

The project was developed in 6 phases, each on a separate branch:

### Phase 1: Foundation & Platform Setup
**Branch**: `phase-1-foundation`
- Database schema design (7 tables)
- Alembic migrations setup
- SQLAlchemy models
- Core configuration management

### Phase 2: Core API Layer
**Branch**: `phase-2-core-api`
- FastAPI application setup
- FR-1: Requisition Request API
- FR-2: Match Response API
- FR-3: Skill Availability Bulk Upsert
- Pydantic schemas and validation

### Phase 3: LangGraph Integration
**Branch**: `phase-3-langgraph-integration`
- LangGraph state graph setup
- State schema design
- Agent topology implementation
- OpenAI integration

### Phase 4: AI Matching Engine
**Branch**: `phase-4-matching-engine`
- 6 specialized AI agents:
  - JD Parsing Agent
  - Skill Normalization Agent
  - Matching & Scoring Agent
  - Availability Evaluation Agent
  - Result Aggregation Agent
  - Explanation Generation Agent
- Multi-agent orchestration
- Prompt engineering

### Phase 5: Security & Observability
**Branch**: `phase-5-security-observability`
- OAuth2 authentication (client credentials)
- JWT token management
- Secrets management (environment-based)
- Prometheus metrics
- Audit trail logging
- 51 passing tests

### Phase 6: Hardening & Scale Readiness
**Branch**: `phase-6-hardening-scale`
- k6 performance test suite
- Load testing (100+ concurrent users)
- Stress testing (400 users)
- Scalability validation (5x data)
- Idempotent retry testing
- Performance targets: P95<2s, P99<5s

## 🤝 Contributing

### Development Workflow

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make changes and test**
   ```bash
   pytest
   black src/ tests/
   ruff check src/ tests/
   ```

3. **Commit with conventional commits**
   ```bash
   git commit -m "feat: add new feature"
   git commit -m "fix: resolve bug in matching logic"
   git commit -m "docs: update API documentation"
   ```

4. **Push and create PR**
   ```bash
   git push origin feature/your-feature-name
   ```

### Code Style

- **Formatting**: Black (100 char line length)
- **Linting**: Ruff
- **Type Hints**: Use Python type annotations
- **Docstrings**: Google style docstrings

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

## 📄 License

This project is proprietary and confidential. Unauthorized copying or distribution is prohibited.

## 👥 Authors

- **Aarya Bhosale** - Initial implementation
- **InfoBeans Development Team**

## 📞 Support

For issues or questions:
- Create an issue in the GitHub repository
- Contact the development team at support@infobeans.com

## 🔗 Links

- **API Documentation**: http://localhost:8000/docs
- **GitHub Repository**: https://github.com/aaryaa-infobeans/ib-job-skill-mapping-system
- **Specification Documents**: [specs/](specs/)
- **Performance Testing Guide**: [docs/phase-6-testing-guide.md](docs/phase-6-testing-guide.md)

---

**Version**: 0.1.0  
**Last Updated**: March 12, 2026
