# Logical Data Model

## Entity Relationship Diagram (ERD)

### Entities

#### auth_clients
- **id**: Primary Key, SmallInt, Auto-generated.
- **client_name**: String, Max Length 100, Not Null.
- **client_code**: String, Max Length 50, Unique, Not Null.
- **client_secret_hash**: String, Max Length 255, Not Null.
- **auth_type**: Enum ('OAUTH', 'API_KEY', 'SAML'), Default 'OAUTH', Not Null.
- **is_active**: Boolean, Default True, Not Null.
- **created_at**: Timestamp, Default Current Timestamp, Not Null.

#### auth_access_tokens
- **id**: Primary Key, Int, Auto-generated.
- **auth_client_id**: Foreign Key to `auth_clients(id)`, SmallInt, Not Null.
- **access_token**: String, Max Length 255, Unique, Not Null.
- **expires_at**: Timestamp, Not Null.
- **is_revoked**: Boolean, Default False, Not Null.
- **issued_at**: Timestamp, Default Current Timestamp, Not Null.

#### requisition_status_master
- **status_id**: Primary Key, SmallInt.
- **status_key**: String, Max Length 40, Unique, Not Null.
- **status_message**: String, Max Length 255, Not Null.

### Relationships

- `auth_access_tokens.auth_client_id` → `auth_clients.id` (On Delete Cascade).

### Notes

- Indexes:
  - `auth_access_tokens`: `idx_token_client` on `auth_client_id`, `idx_token_expiry` on `expires_at`.
- Constraints:
  - `auth_clients.auth_type` must be one of ('OAUTH', 'API_KEY', 'SAML').