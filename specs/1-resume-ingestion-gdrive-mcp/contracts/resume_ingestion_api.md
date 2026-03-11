# API Contract: Resume Ingestion

## Endpoint: POST /api/v1/resume-ingestion

### Request

#### Headers
- `Authorization`: Bearer token for authentication.
- `Content-Type`: application/json

#### Body
```json
{
  "document_id": "string",
  "metadata": {
    "location": "string",
    "work_type": "string",
    "availability": "string",
    "certifications": ["string"],
    "skills": ["string"]
  }
}
```

### Response

#### Success (200 OK)
```json
{
  "status": "success",
  "message": "Resume ingested successfully.",
  "embedding_id": "uuid"
}
```

#### Error (400 Bad Request)
```json
{
  "status": "error",
  "message": "Invalid input data."
}
```

#### Error (401 Unauthorized)
```json
{
  "status": "error",
  "message": "Unauthorized access."
}
```

#### Error (500 Internal Server Error)
```json
{
  "status": "error",
  "message": "An unexpected error occurred."
}
```