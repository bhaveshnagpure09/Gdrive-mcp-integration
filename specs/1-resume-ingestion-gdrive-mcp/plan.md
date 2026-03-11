# Implementation Plan: Resume Ingestion via Gdrive MCP

**Branch**: `1-resume-ingestion-gdrive-mcp` | **Date**: 2026-03-11 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1-resume-ingestion-gdrive-mcp/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

This feature enables resume ingestion from Google Drive MCP. It introduces a FastAPI endpoint to fetch resumes from connected MCP storage systems, process the resume text, generate embeddings, and store them in PostgreSQL with pgvector. The existing matching workflow remains unchanged.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: FastAPI, PostgreSQL, LangChain, embedding-gemma-300m  
**Storage**: PostgreSQL with pgvector  
**Testing**: pytest  
**Target Platform**: Linux server  
**Project Type**: Web service  
**Performance Goals**: Sub-second retrieval for stored embeddings, batch processing within minutes  
**Constraints**: OAuth2 authentication, PII scrubbing, horizontal scalability  
**Scale/Scope**: 10k resumes, 100 concurrent users

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **API-First**: The feature exposes a REST API for resume ingestion.
- **AI-Driven Matching**: Embeddings are generated using `embedding-gemma-300m`.
- **Data-Centric Architecture**: PostgreSQL is used for embedding storage.
- **Security by Design**: OAuth2 authentication and PII scrubbing are implemented.
- **Observability**: Logging and metrics are included.

## Project Structure

### Documentation (this feature)

```text
specs/1-resume-ingestion-gdrive-mcp/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/
├── app/
│   ├── api/
│   │   ├── endpoints/
│   │   │   └── resume_ingestion.py
│   │   └── __init__.py
│   ├── core/
│   │   ├── mcp_client.py
│   │   └── pii_scrubber.py
│   ├── db/
│   │   ├── models.py
│   │   └── vector_storage.py
│   └── services/
│       ├── embedding_generator.py
│       └── resume_processor.py
└── tests/
    ├── integration/
    │   └── test_resume_ingestion.py
    └── unit/
        ├── test_embedding_generator.py
        ├── test_mcp_client.py
        └── test_resume_processor.py
```

## Phases

### Phase 0: Outline & Research

1. Research Google Drive API for document retrieval.
2. Identify best practices for PII scrubbing.
3. Evaluate embedding-gemma-300m for resume embeddings.
4. Document findings in `research.md`.

### Phase 1: Design & Contracts

1. Define data model for `team_member_embeddings` in `data-model.md`.
2. Create API contract for resume ingestion in `contracts/`.
3. Write `quickstart.md` for feature setup.
4. Update agent context with new dependencies.

### Phase 2: Implementation

1. Implement FastAPI endpoint in `resume_ingestion.py`.
2. Develop MCP client for Google Drive in `mcp_client.py`.
3. Create PII scrubbing utility in `pii_scrubber.py`.
4. Build embedding generator in `embedding_generator.py`.
5. Integrate vector storage in `vector_storage.py`.

### Phase 3: Testing

1. Write unit tests for all new modules.
2. Develop integration tests for the endpoint.
3. Conduct end-to-end tests for the ingestion workflow.

### Phase 4: Deployment

1. Deploy the feature branch to staging.
2. Validate functionality in staging.
3. Merge to `master` after approval.

## Risks & Mitigation

1. **Google API Quotas**: Use exponential backoff for retries.
2. **PII Scrubbing Failures**: Log errors and skip affected resumes.
3. **Embedding Generation Errors**: Implement fallback mechanisms.
4. **Database Constraints**: Validate data before insertion.

## Expected Outcome

- Resumes can be ingested via FastAPI endpoint.
- Embeddings are stored in PostgreSQL with pgvector.
- Existing matching workflow remains functional.
- System handles edge cases gracefully.
