# Data Model: Resume Ingestion via Gdrive MCP

## team_member_embeddings Table

### Columns

1. **team_member_id** (UUID, Primary Key): Unique identifier for the candidate.
2. **embedding** (Vector): Vector embedding generated from the profile text.
3. **profile_text** (Text): Full text used to generate the embedding, including structured metadata and resume content.
4. **metadata** (JSON): Structured attributes used for filtering and ranking.
5. **created_at** (Timestamp): Timestamp of vector creation.

### Example Metadata

```json
{
  "location": "Bangalore",
  "work_type": "remote",
  "availability": "available",
  "certifications": ["AWS Certified Developer"],
  "skills": ["Python", "FastAPI", "LangChain"],
  "storage_source": "gdrive",
  "document_id": "google_doc_id"
}
```

## Notes

- The `embedding` column uses the `pgvector` extension in PostgreSQL.
- Metadata is stored as JSON for flexibility in filtering and ranking.
- Ensure proper indexing on frequently queried fields in `metadata`.