# Chatbot Features

## Overview

The chatbot provides a conversational interface for natural language requests, turning questions into SQL or code and guiding users through multi-turn analysis with real-time feedback.

## Core Capabilities

- Multi-conversation management (create, rename, delete, switch) with auto-titles.
- Query modes for SQL, R, SAS, and Python generation plus object search.
- Streaming responses via SSE with step-by-step status updates.
- Ambiguity handling with an explicit clarification flow for uncertain intent.
- Rich message payloads that attach discovery context, SQL results, and analysis metadata.

## Conversation Storage

- Conversations are persisted locally in browser storage for quick resume.
- When user accounts are enabled, conversations can also sync to the backend with per-user scoping and metadata preservation.

## Result Experience

- Generated SQL or code is returned with explanations and validation feedback.
- Optional execution results include profiling, insights, and visualization recommendations.
- Chart intent detection can translate natural language hints into chart type overrides.

## Related Documentation

- Agent process: [AGENT_PROCESS.md](AGENT_PROCESS.md)
- Vector schema: [VECTOR_SCHEMA.md](VECTOR_SCHEMA.md)
- Frontend chat UI: [FRONTEND.md](FRONTEND.md)
- SQL generation pipeline: [GENERATE_SQL.md](GENERATE_SQL.md)
- Request-to-code flow: [REQUEST_TO_CODE_FLOW.md](REQUEST_TO_CODE_FLOW.md)
- Planning / ask mode: [PLANNING_MODE_FLOW.md](PLANNING_MODE_FLOW.md)
- User conversation storage: [USER_MANAGEMENT.md](USER_MANAGEMENT.md)
