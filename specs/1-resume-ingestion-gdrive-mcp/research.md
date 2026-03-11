# Research for Resume Ingestion via Gdrive MCP

## Google Drive API for Document Retrieval
- Research the Google Drive API documentation to understand the endpoints and authentication mechanisms required for document retrieval.
- Identify the scopes required for accessing files.
- Explore the use of service accounts for automated access.

## Best Practices for PII Scrubbing
- Investigate common techniques for identifying and removing Personally Identifiable Information (PII) from documents.
- Evaluate existing libraries or tools for PII scrubbing.
- Document the trade-offs between accuracy and performance for different approaches.

## Embedding-Gemma-300m for Resume Embeddings
- Analyze the capabilities of the embedding-gemma-300m model for generating embeddings from resumes.
- Compare its performance with other embedding models.
- Identify any preprocessing steps required for optimal results.

# Research Findings: Resume Ingestion via Gdrive MCP

## Google Drive API

- **Capabilities**: Fetch document content, list files, and manage permissions.
- **Authentication**: OAuth2 required; token.json generated for reuse.
- **Quota Management**: Implement exponential backoff for retries.

## PII Scrubbing

- **Best Practices**:
  - Use regex patterns for sensitive data detection.
  - Mask or remove PII before further processing.
- **Tools**: Python libraries like `pii-extract` and `re`.

## Embedding Model: embedding-gemma-300m

- **Performance**: Optimized for text embeddings.
- **Input**: Structured profile text.
- **Output**: 300-dimensional vector.

## Recommendations

1. Use Google Drive API for document retrieval.
2. Implement robust PII scrubbing before embedding generation.
3. Leverage embedding-gemma-300m for consistent vector generation.