# Admin Features

## Overview

The admin experience covers privileged workflows for schema discovery, knowledge curation, value indexing, skills management, and system configuration. Access is restricted to users with the `admin` role, and all admin endpoints live under `/api/v1/admin`.

## Admin Panel (UI)

### 1) Schema Manager
- View schema index status and database inspection results.
- Sync individual tables, batch sync, or sync all schemas when the index is empty.
- Import/export schema metadata via Excel.
- Edit schema descriptions, delete schemas, or clear all schemas.

### 2) Few-Shot Manager (Knowledge Base)
- Add, edit, and delete example queries.
- Bulk import/export via Excel.
- Track verification status and maintain high-quality examples for LLM context.

### 3) Value Index Manager
- Upload values via Excel or CSV with append/replace modes.
- Search, delete, export, or clear indexed values.
- Download a template file for consistent value ingestion.

### 4) Contribution Manager
- Review user-submitted examples.
- Approve or reject contributions; edit content before approval.

### 5) Skills Manager
- Browse a structured skills tree (data sources, data groups, tables).
- View rendered markdown, inspect raw markdown, or edit files directly.
- CRUD operations for skills entities with automatic index maintenance.
- Keyword-based search and index regeneration for fast discovery.

### 6) Data Sources Manager
- Create, update, and delete data sources.
- Test connections, toggle enablement, set primary sources.
- Scan sources and inspect schema trees for discovery workflows.

### 7) User Manager
- List, create, update, and delete users.
- Assign roles (admin or user) and toggle active status.
- Regenerate API keys for users.
- View user stats and activity logs.

### 8) Settings
- Configure LLM settings (model, endpoint, API key).
- Update database connection details.
- Fetch model lists, verify settings, and test connections.
- Manage vector store settings and backups.

## Admin API Highlights

Common admin endpoints include:
- Schema indexing: `POST /admin/schema/sync`, `POST /admin/schema/sync-all`, `POST /admin/schema/batch-sync`, `GET /admin/schema/status`, `PUT /admin/schema/description`, `DELETE /admin/schema`, `POST /admin/schema/clear`, import/export endpoints.
- Few-shot examples: `GET /admin/fewshots`, `POST /admin/fewshots`, `DELETE /admin/fewshots/{id}`, import/export endpoints.
- Value index: `POST /admin/ingest-values`, `GET /admin/values`, `GET /admin/values/search`, `DELETE /admin/values/{id}`, `POST /admin/values/clear`, `GET /admin/values/template`, export endpoint.
- Contributions: `GET /admin/contributions`, `POST /admin/contributions/approve`, `DELETE /admin/contributions/{id}`.
- Skills: CRUD endpoints under `/admin/skills/*`, markdown read/write, index search, and index regeneration.
- Users: CRUD endpoints under `/admin/users`, user stats and activity endpoints.
- Settings and data sources: endpoints under `/admin/settings` and `/admin/data-sources`.

## Related Documentation

- Backend API: [docs/BACKEND_API.md](BACKEND_API.md)
- User management and roles: [docs/USER_MANAGEMENT.md](USER_MANAGEMENT.md)
- Skills manager and CRUD: [docs/SKILLS_IMPLEMENTATION_SUMMARY.md](SKILLS_IMPLEMENTATION_SUMMARY.md)
- Skills markdown editor: [docs/SKILLS_MARKDOWN_EDITOR.md](SKILLS_MARKDOWN_EDITOR.md)
- Schema index search: [docs/SCHEMA_INDEX_SEARCH_FEATURE.md](SCHEMA_INDEX_SEARCH_FEATURE.md)
- Schema sync feature: [docs/SCHEMA_SYNC_FEATURE.md](SCHEMA_SYNC_FEATURE.md)
- Value index feature: [docs/VALUE_INDEX_FEATURE.md](VALUE_INDEX_FEATURE.md)
