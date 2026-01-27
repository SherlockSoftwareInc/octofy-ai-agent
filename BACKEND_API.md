# Backend API Reference

This document summarizes the backend features and HTTP endpoints so other apps can call the API.

## Base URL and Auth

- Base URL: `/api/v1`
- Root health: `GET /` -> `{"message":"Octofy AI Agent API is running"}`
- OpenAPI: `GET /api/v1/openapi.json`
- Auth header: `X-API-Key: <api-key>`
  - Required for all endpoints unless noted as "No auth".
  - Key is validated against `.env` `API_KEY` or `app/core/config.py` default.

## Common Response Errors

- `400 Bad Request` -> `{"detail":"..."}`
- `401 Unauthorized` -> `{"detail":"Invalid or missing API key"}`
- `404 Not Found` -> `{"detail":"..."}`
- `500 Internal Server Error` -> `{"detail":"..."}`

## Discovery

Find relevant tables, similar queries, and glossary terms for a natural language question.

- `POST /api/v1/discovery` (auth)
  - Body:
    - `query` (string, required)
    - `top_k` (int, optional, default 5)
  - Response:
    - `query` (string)
    - `reasoning` (string)
    - `context`:
      - `relevant_tables` (array of `TableSchema`)
      - `similar_queries` (any)
      - `glossary_terms` (object)

- `POST /api/v1/test` (auth)
  - Response: `{"message":"Test endpoint works"}`

## SQL/Code Generation (Streaming SSE)

Generates SQL or code with Server-Sent Events (`text/event-stream`).

Event formats:

- Status event:
  - `data: {"step_id":1,"message":"...","type":"status","details":{...},"timestamp":1234567890.0}`
- Result event:
  - `data: {"type":"result","payload":{"sql":"...","explanation":"...","query_type":"database","context_text":"...","context_history":[...]}}`
- Error event:
  - `data: {"type":"error","message":"..."}`

Endpoints (all auth):

- `POST /api/v1/generation/generate-sql`
- `POST /api/v1/generation/generate-r`
- `POST /api/v1/generation/generate-sas`
- `POST /api/v1/generation/generate-python`

Request body (`GenerateSQLRequest`):

- `query` (string, required)
- `context` (DiscoveryContext, optional)
- `previousSQL` (string, optional)
- `queryHistory` (string, optional)
- `forceGeneral` (bool, optional, default false)
- `queryMode` (`"generate"` or `"search"`, optional, default `"generate"`)
- `table_override` (string array of `schema.table`, optional)

Example SSE client (curl):

```
curl -N -H "X-API-Key: <api-key>" \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"Top 10 customers by revenue\"}" \
  http://<host>/api/v1/generation/generate-sql
```

## Schema Lookup

- `GET /api/v1/schema/{object_name}` (no auth)
  - `object_name` format: `schema.table` (brackets are stripped)
  - Response: `TableSchema`

`TableSchema`:

- `schema_name` (string)
- `table_name` (string)
- `table_type` (string, default `"table"`)
- `description` (string, optional)
- `columns` (array of `{name,data_type,description}`)

## Admin - Schema Management

All endpoints below require auth.

- `GET /api/v1/admin/schema/status`
  - Response: array of `AdminSchemaStatus`

- `POST /api/v1/admin/schema/sync?schema=<schema>&table=<table>`
  - Response: `{"status":"success","message":"Synced schema.table"}`

- `POST /api/v1/admin/schema/sync-full`
  - Response: `{"status":"success","message":"Successfully synced all schemas and rebuilt vector index"}`

- `POST /api/v1/admin/schema/batch-sync`
  - Body: `{ "table_names": ["dbo.Customers","Orders"] }`
  - Response: `BatchSyncResponse`

- `PUT /api/v1/admin/schema/description?schema=<schema>&table=<table>&description=<text>`
  - Response: `{"status":"success","message":"Updated description for schema.table"}`

- `DELETE /api/v1/admin/schema?schema=<schema>&table=<table>`
  - Response: `{"status":"success","message":"Deleted schema.table from vector store"}`

- `GET /api/v1/admin/schema/export`
  - Response: Excel file download (`schema_index_*.xlsx`)

- `POST /api/v1/admin/ingest-schemas` (multipart)
  - Form file field: `file` (Excel)
  - Query: `mode=append|replace` (default `append`)
  - Response: `{rows_processed,total_rows,...}`
  - Progress: `GET /api/v1/admin/ingest-progress` (no auth, SSE)

- `GET /api/v1/admin/schema/template`
  - Response: Excel template download

- `POST /api/v1/admin/schema/clear`
  - Response: `{"status":"success","message":"Cleared all schemas from vector store"}`

`AdminSchemaStatus`:

- `schema_name`, `table_name`, `table_type`
- `is_indexed` (bool)
- `description` (string, optional)
- `column_count` (int)
- `last_updated` (string, optional)

## Admin - Few-Shot / Knowledge Base

All endpoints require auth.

- `GET /api/v1/admin/fewshots`
  - Response: array of `FewShotItem`

- `POST /api/v1/admin/fewshots`
  - Body: `FewShotItem` (id is optional)
  - Response: `{"status":"success"}`

- `DELETE /api/v1/admin/fewshots/{item_id}`
  - Response: `{"status":"success"}`

- `GET /api/v1/admin/fewshots/export`
  - Response: Excel file download (`knowledge_base_*.xlsx`)

- `POST /api/v1/admin/ingest-fewshots` (multipart)
  - Form file field: `file` (Excel)
  - Query: `mode=append|replace` (default `append`)
  - Response: `{rows_processed,total_rows,...}`
  - Progress: `GET /api/v1/admin/ingest-progress` (no auth, SSE)

`FewShotItem`:

- `id` (string, optional)
- `question` (string)
- `sql_query` (string)
- `knowledge_type` (string, default `"sql_query"`)
- `verified` (bool)

## Admin - Value Index

All endpoints require auth.

- `POST /api/v1/admin/ingest-values` (multipart)
  - Form file field: `file` (Excel or CSV)
  - Query: `mode=append|replace` (default `append`)
  - Response: `{rows_processed,total_rows,...}`
  - Progress: `GET /api/v1/admin/ingest-progress` (no auth, SSE)

- `GET /api/v1/admin/values/search?query=<text>&top_k=50`
  - Response: array of objects

- `GET /api/v1/admin/values`
  - Response: array of objects

- `DELETE /api/v1/admin/values/{item_id}`
  - Response: `{"status":"success","message":"Deleted value <id>"}`

- `POST /api/v1/admin/values/clear`
  - Response: `{"status":"success","message":"Cleared all values from index"}`

- `GET /api/v1/admin/values/template`
  - Response: Excel template download

- `GET /api/v1/admin/values/export`
  - Response: Excel file download (`value_index_*.xlsx`)

## Admin - Vector Store Backup

All endpoints require auth.

- `GET /api/v1/admin/vector-store/backup`
  - Response: JSON file download (`vector_store_backup_*.json`)

## Settings and Connectivity

All endpoints require auth.

- `GET /api/v1/admin/settings`
  - Response: `AgentSettings` (masked secrets)

- `PUT /api/v1/admin/settings`
  - Body: `AgentSettings`
  - Response: updated `AgentSettings`

- `POST /api/v1/admin/test-connection`
  - Body: `ConnectionTestRequest`
  - Response: `ConnectionTestResponse`

- `GET /api/v1/admin/models`
  - Response: `{"models":[{id,name,provider}]}` (fallback if provider not configured)

- `POST /api/v1/admin/fetch-models`
  - Body: `{ "llm_endpoint": "...", "llm_api_key": "..." }`
  - Response: `{ "models": [...] }`

- `POST /api/v1/admin/build-connection-string`
  - Body: `ConnectionTestRequest`
  - Response: `{ "connection_string":"...", "connection_string_masked":"...", "encrypted":"..." }`

- `POST /api/v1/admin/verify-settings`
  - Response:
    - `db_connected`, `db_message`
    - `llm_connected`, `llm_message`
    - `milvus_connected`, `milvus_message`

## Contributions

Public contribution submission plus admin review endpoints.

- `POST /api/v1/contributions` (auth)
  - Body: `ContributionRequest`
  - Validations:
    - `question` max 2000 chars
    - `sql_query` max 4000 chars
    - `user_id` max 128 chars
  - Response: `ContributionResponse` (includes similarity warning/score)

Admin endpoints (auth):

- `GET /api/v1/admin/contributions`
  - Response: array of `ContributionItem` (pending)

- `POST /api/v1/admin/contributions/approve`
  - Body: `ApproveContributionRequest`
  - Response: `ApproveContributionResponse`

- `DELETE /api/v1/admin/contributions/{contribution_id}`
  - Response: `{"status":"success","message":"Contribution rejected and removed."}`

## SSE Progress Endpoint

Upload/ingestion operations report progress via SSE:

- `GET /api/v1/admin/ingest-progress` (no auth)
  - Response stream events:
    - `{"current":0,"total":100,"percentage":0,"status":"processing|complete|error"}`

Example SSE client (fetch):

```
const source = new EventSource("http://<host>/api/v1/admin/ingest-progress");
source.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data);
};
```

## Quick Auth Example

```
curl -H "X-API-Key: <api-key>" http://<host>/api/v1/admin/schema/status
```
