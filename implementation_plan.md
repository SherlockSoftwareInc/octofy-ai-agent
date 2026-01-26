# Implementation Plan: Save First, Verify Later for Agent Settings

## Changes Made

### Backend
1.  **Modified `app/api/endpoints/settings.py`**:
    *   Added a new endpoint `POST /verify-settings`.
    *   This endpoint loads the *currently saved* settings from disk.
    *   It attempts to connect to the Target Database (using the decrypted connection string).
    *   It attempts to connect to the LLM Provider (fetching models as a liveness check).
    *   Returns a structured result: `{ db_connected, db_message, llm_connected, llm_message }`.

### Frontend
1.  **Modified `frontend/src/api/client.ts`**:
    *   Added `VerifySettingsResponse` interface.
    *   Added `verifySettings` method to `api.admin`.

2.  **Modified `frontend/src/pages/Admin/Settings.tsx`**:
    *   Updated `handleSave` function.
    *   It now performs `api.admin.updateSettings(settings)` first.
    *   Upon success, it calls `api.admin.verifySettings()`.
    *   The UI displays a combined status message: success if verified, or specific error messages if verification failed despite saving.

## Verification
*   **Database**: The system uses the encrypted connection string stored in `agent_settings.json` (decrypted on the fly by the backend) to verify connectivity. This solves the issue where the frontend might not have the password if it wasn't re-entered.
*   **LLM**: The system uses the stored endpoint and API key to fetch models, verifying that the LLM service is reachable and authorized.
