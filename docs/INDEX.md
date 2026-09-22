# Documentation Index

Main index of system design and feature documentation.

Start here for the current generate pipeline:

1. [AGENT_PROCESS.md](AGENT_PROCESS.md) — stages, branches, attempt loop, constants
2. [VECTOR_SCHEMA.md](VECTOR_SCHEMA.md) — collections, fields, embeddings, `source_id` partitioning
3. [REQUEST_TO_CODE_FLOW.md](REQUEST_TO_CODE_FLOW.md) — HTTP/SSE path
4. [DISCOVERY_STRATEGY_IMPLEMENTATION.md](DISCOVERY_STRATEGY_IMPLEMENTATION.md) — KB-first + RRF

Building or re-implementing the backend?

- [SQL_GENERATION_BACKEND_BLUEPRINT.md](SQL_GENERATION_BACKEND_BLUEPRINT.md) — end-to-end build specification for the whole backend SQL-generation process (§01–§16: contracts, constants, pipeline stages, verbatim prompts, semantic layer, ingestion, acceptance tests, parity pitfalls). Written so an AI coding agent can rebuild the agent from the document alone.

## Core System
- [SQL_GENERATION_BACKEND_BLUEPRINT.md](SQL_GENERATION_BACKEND_BLUEPRINT.md) — full implementation blueprint (build spec) for the SQL-generating backend
- [AGENT_PROCESS.md](AGENT_PROCESS.md) — canonical generate pipeline (route, discover, attempt loop)
- [plans/2026-09-20-conversational-context-and-refinement.md](plans/2026-09-20-conversational-context-and-refinement.md) — scenario routing, coreference rewrite, session filter state, prompt split
- [VECTOR_SCHEMA.md](VECTOR_SCHEMA.md) — vector collection contract (`schemas`, few-shots, values, data groups)
- [BACKEND_API.md](BACKEND_API.md)
- [FRONTEND.md](FRONTEND.md)
- [REQUEST_TO_CODE_FLOW.md](REQUEST_TO_CODE_FLOW.md)
- [GENERATE_SQL.md](GENERATE_SQL.md)
- [PLANNING_MODE_FLOW.md](PLANNING_MODE_FLOW.md)
- [CHATBOT.md](CHATBOT.md)

## Admin & Operations
- [Admin.md](Admin.md)
- [SECURITY_FIXES.md](SECURITY_FIXES.md)

## User Management & Auth
- [USER_MANAGEMENT.md](USER_MANAGEMENT.md)
- [GETTING_STARTED_USER_MANAGEMENT.md](GETTING_STARTED_USER_MANAGEMENT.md)
- [WINDOWS_AUTH_FLOW_DIAGRAM.md](WINDOWS_AUTH_FLOW_DIAGRAM.md)
- [WINDOWS_AUTH_QUICKSTART.md](WINDOWS_AUTH_QUICKSTART.md)
- [WINDOWS_AUTH_EXECUTION_VERIFICATION.md](WINDOWS_AUTH_EXECUTION_VERIFICATION.md)

## Discovery & Search
- [DISCOVERY_STRATEGY_IMPLEMENTATION.md](DISCOVERY_STRATEGY_IMPLEMENTATION.md) — KB-first + RRF ranking
- [NATURAL_LANGUAGE_SEARCH_GUIDE.md](NATURAL_LANGUAGE_SEARCH_GUIDE.md)
- [SCHEMA_INDEX_SEARCH_FEATURE.md](SCHEMA_INDEX_SEARCH_FEATURE.md)
- [TURN_TYPE_FAST_DETECTION.md](TURN_TYPE_FAST_DETECTION.md)

## Knowledge Base & Skills
- [SKILLS_CRUD_API.md](SKILLS_CRUD_API.md)
- [SKILLS_QUICK_REFERENCE.md](SKILLS_QUICK_REFERENCE.md)
- [SKILLS_UI_GUIDE.md](SKILLS_UI_GUIDE.md)
- [SKILLS_MARKDOWN_EDITOR.md](SKILLS_MARKDOWN_EDITOR.md)
- [MARKDOWN_VIEW_EDIT_FEATURE.md](MARKDOWN_VIEW_EDIT_FEATURE.md)

## Value Index & Uploads
- [VALUE_INDEX_FEATURE.md](VALUE_INDEX_FEATURE.md)
- [VALUE_INDEX_QUICKSTART.md](VALUE_INDEX_QUICKSTART.md)
- [EXCEL_UPLOAD_FEATURE.md](EXCEL_UPLOAD_FEATURE.md)
- [EXCEL_UPLOAD_QUICKSTART.md](EXCEL_UPLOAD_QUICKSTART.md)

## Schema Management
- [SCHEMA_SYNC_FEATURE.md](SCHEMA_SYNC_FEATURE.md)
