# Resume Ingestion via Gdrive MCP

## Overview

Add a new feature to the existing system that enables resume ingestion from gdrive MCP. This feature will extend the current system without modifying the existing matching workflow or ranking pipeline.

The system will expose a FastAPI endpoint that allows resumes to be fetched from connected mcp storage systems. The endpoint will support selecting the storage source and optionally providing a document identifier.

Using MCP, the system will retrieve resume content from the selected storage source, process the resume text, generate embeddings, and store the vectors in the system’s vector database. Once the embeddings are stored, the existing workflow will continue unchanged and the matching agent will use the stored embeddings for its processing and ranking.

Although the architecture must support multiple storage systems through MCP servers, the initial implementation will focus on **Google Drive integration**

## FastAPI Endpoint

Create a FastAPI endpoint responsible for triggering resume ingestion.

### Endpoint Behavior

The endpoint must allow two inputs:

1. **Resume Identifier Option**

   * Provide a **Google Doc ID**
   * Or select **All Resumes**

2. **Storage Source Selection**

   * Select the storage system from which the resume should be fetched.

Example storage sources supported by MCP servers:

* Google Drive
* Azure Blob Storage
* File Storage
* Other external storage systems connected through MCP

For the initial implementation, only **Google Drive MCP server** must be implemented.

---

## Endpoint Request Examples

### Single Resume

Request payload example:

{
"doc_id": "google_doc_id",
"storage": "gdrive"
}

### Batch Processing

Request payload example:

{
"doc_id": null,
"fetch_all": true,
"storage": "gdrive"
}

### Multi Storage Fetch (Future)

Request payload example:

{
"fetch_all": true,
"storage": "all"
}

If `storage = all`, the system must fetch resumes from all connected MCP storage servers.

---

## Resume Retrieval using MCP

The system must use MCP to retrieve resume content.

The ingestion service will act as an MCP client and call a storage-specific MCP server.

For the first implementation, build a **Google Drive MCP Server** that exposes tools capable of:

* Fetching Google Doc content using document ID
* Listing all resume documents stored in Google Drive
* Returning the extracted resume text to the ingestion service

---

## Resume Processing Pipeline

After the resume text is retrieved through MCP, the following processing must occur:

1. Extract plain text from the document.
2. Perform **PII scrubbing** to remove or mask sensitive personal data.
3. Construct the **profile text** using structured information.

Based on the current system logic, profile text must contain:

* Designation
* Base location
* Work mode
* Experience in months
* Skills list
* Certifications
* Resume content extracted from Google Drive

Example structure:

Designation: Software Engineer
Location: Bangalore
Work Mode: Remote
Experience: 48 months
Skills: Python, FastAPI, LangChain
Certifications: AWS Certified Developer
Resume Content: <Extracted resume text>

---

## Embedding Generation

After profile text construction:

Generate embeddings using the model:

**embedding-gemma-300m**

The embedding must be generated from the complete profile text including structured metadata and resume content.

---

## Vector Database Storage

Use **PostgreSQL with pgvector** as the vector database since the existing system already stores embeddings in PostgreSQL.

Vectors must be stored in the table:

team_member_embeddings

Each stored record must include:

### team_member_id

Unique identifier for the candidate.

### embedding

Vector embedding generated from the profile text.

### profile_text

The full text used to generate the embedding, including:

* designation
* location
* work type
* experience
* skills
* certifications
* resume text

### metadata (JSON)

Metadata must contain structured attributes used for filtering and ranking.

Example metadata:

{
"location": "Bangalore",
"work_type": "remote",
"availability": "available",
"certifications": ["AWS Certified Developer"],
"skills": ["Python","FastAPI","LangChain"],
"storage_source": "gdrive",
"document_id": "google_doc_id"
}

### created_at

Timestamp of vector creation.

---

## Google Drive MCP Server

Implement a custom MCP server that interacts with Google Drive.

The MCP server must expose tools for:

* Fetching a single resume using Google Doc ID
* Listing all resumes available in Google Drive

---

## Google Drive MCP Server Setup

### Setup

1. Create OAuth Desktop credentials in Google Cloud Console.
2. Download the credentials file and save it as:

credentials.json

3. Ensure the Google Docs containing resumes are shared with the Google account that will authenticate.

---

### Notes

* During the first run, the system will open a browser window to authenticate with Google.
* After authentication, a file named **token.json** will be generated.
* Subsequent runs will reuse the existing token.json without requiring browser login again.

---

## System Processing Flow

1. Request is received at the FastAPI endpoint.
2. User selects:

   * resume identifier (doc_id or all)
   * storage source.
3. The ingestion service calls the appropriate MCP server.
4. MCP server fetches the resume text.
5. Resume text is cleaned using PII scrubbing.
6. Profile text is constructed.
7. Embeddings are generated using **embedding-gemma-300m**.
8. Embeddings and metadata are stored in PostgreSQL with pgvector.
9. The existing workflow continues without modification.
10. Matching agents use the stored embeddings during candidate matching and ranking.

---

## Test Cases

### 1. Endpoint Tests

Verify endpoint behavior:

* Valid Google Doc ID ingestion works correctly
* Request without doc ID triggers batch ingestion
* Storage selection works correctly
* Invalid storage value returns appropriate error
* Missing request parameters handled gracefully

---

### 2. MCP Server Tests

Verify MCP functionality:

* Successful Google authentication
* token.json generation on first run
* token reuse on subsequent runs
* Resume retrieval using valid Google Doc ID
* Listing all resume documents
* Handling invalid document IDs
* Handling permission denied errors

---

### 3. Resume Processing Tests

Verify:

* Resume text extraction is successful
* PII scrubbing removes sensitive data
* Profile text is constructed correctly
* Structured attributes are included properly

---

### 4. Embedding Generation Tests

Verify:

* embedding-gemma-300m generates embeddings successfully
* Embedding vector dimensions are valid
* Embeddings generated for both single and batch ingestion
* System handles embedding failures correctly

---

### 5. Vector Database Tests

Verify:

* Embeddings stored in pgvector correctly
* Metadata JSON stored correctly
* profile_text matches processed resume content
* created_at timestamp stored correctly
* Duplicate resume ingestion handled properly

---

## End-to-End System Tests

### Test Case 1: Single Resume End-to-End

1. Call FastAPI endpoint with valid Google Doc ID
2. MCP retrieves resume text
3. PII scrubbing runs
4. Embedding generated
5. Vector stored in database
6. Matching agent successfully retrieves candidate vector

Expected Result: Candidate is available for ranking.

---

### Test Case 2: Batch Resume Ingestion

1. Call endpoint without doc ID
2. MCP lists all resumes
3. Each resume processed sequentially
4. Embeddings generated for each
5. Vectors stored in database

Expected Result: All candidates become available to matching agents.

---

### Test Case 3: Matching Workflow Continuity

1. Ingest resume
2. Run matching agent pipeline

Expected Result: Matching agent uses stored embeddings for ranking without workflow modification.

---

## Edge Cases

The system must correctly handle the following:

1. Invalid Google Doc ID
2. Google Doc not shared with authenticated account
3. Empty resume documents
4. Network failures during MCP calls
5. OAuth authentication failures
6. Corrupted token.json
7. Duplicate resume ingestion
8. Extremely large resume files
9. Resume text extraction failures
10. Embedding generation failures
11. Database insertion failures
12. MCP server downtime

All failures must be logged and appropriate responses returned.

---

## Expected Outcome

After implementation:

* Resumes can be ingested through a FastAPI endpoint.
* MCP retrieves resumes from Google Drive.
* Resume text is cleaned and processed.
* Embeddings are generated using **embedding-gemma-300m**.
* Embeddings are stored in PostgreSQL with pgvector.
* The existing matching workflow continues unchanged.
* Matching agents consume stored embeddings for candidate ranking.