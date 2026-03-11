# Quickstart: Resume Ingestion via Gdrive MCP

## Prerequisites

1. Ensure you have Python 3.9+ installed.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up environment variables:
   - `GOOGLE_DRIVE_API_KEY`: API key for accessing Google Drive.
   - `DATABASE_URL`: Connection string for the PostgreSQL database.

## Steps

1. **Run Database Migrations**
   ```bash
   alembic upgrade head
   ```

2. **Start the Application**
   ```bash
   uvicorn src.app.main:app --reload
   ```

3. **Test the API**
   - Use the `/api/v1/resume-ingestion` endpoint to ingest resumes.
   - Example request:
     ```bash
     curl -X POST \
       -H "Authorization: Bearer <token>" \
       -H "Content-Type: application/json" \
       -d '{"document_id": "doc123", "metadata": {"location": "NY"}}' \
       http://localhost:8000/api/v1/resume-ingestion
     ```

4. **Verify Data**
   - Check the `team_member_embeddings` table in the database to ensure the data is stored correctly.

## Troubleshooting

- **Authentication Errors**: Ensure the Bearer token is valid.
- **Database Connection Issues**: Verify the `DATABASE_URL` environment variable.
- **Google Drive API Errors**: Check the API key and permissions.