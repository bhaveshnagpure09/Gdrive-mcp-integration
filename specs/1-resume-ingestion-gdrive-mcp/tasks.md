# Tasks for Resume Ingestion via Gdrive MCP

## Phase 0: Outline & Research

- [X] T001 Research Google Drive API for document retrieval.
- [X] T002 Identify best practices for PII scrubbing.
- [X] T003 Evaluate embedding-gemma-300m for resume embeddings.
- [X] T004 Document findings in `research.md`.

## Phase 1: Design & Contracts

- [X] T005 Define data model for `team_member_embeddings` in `data-model.md`.
- [X] T006 Create API contract for resume ingestion in `contracts/`.
- [X] T007 Write `quickstart.md` for feature setup.
- [X] T008 Update agent context with new dependencies.

## Phase 2: Implementation

- [X] T009 Implement FastAPI endpoint in `resume_ingestion.py`.
- [X] T010 Develop MCP client for Google Drive in `mcp_client.py`.
- [X] T011 Create PII scrubbing utility in `pii_scrubber.py`.
- [X] T012 Build embedding generator in `embedding_generator.py`.
- [X] T013 Integrate vector storage in `vector_storage.py`.

## Phase 3: Testing

- [X] T014 Write unit tests for all new modules.
- [X] T015 Develop integration tests for the endpoint.
- [X] T016 Conduct end-to-end tests for the ingestion workflow.

## Phase 4: Deployment

- [X] T017 Deploy the feature branch to staging.
- [X] T018 Validate functionality in staging.
- [ ] T019 Merge to `master` after approval.

## Risks & Mitigation

- [X] T020 Implement exponential backoff for Google API retries.
- [X] T021 Log errors and skip affected resumes for PII scrubbing failures.
- [X] T022 Implement fallback mechanisms for embedding generation errors.
- [X] T023 Validate data before database insertion to handle constraints.