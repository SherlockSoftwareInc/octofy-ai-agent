# AI Settings

The **AI Provider Settings** dialog configures the LLM provider, embedding model, retrieval thresholds, and semantic-layer options used by all built-in AI features in Octofy Professional. It works with any OpenAI-compatible endpoint as well as provider-specific APIs (Anthropic, Google Gemini, Azure OpenAI, and others).

To open the dialog, choose **AI Assistant > AI Settings** from the main window.

## Toolbar

| Button | Description |
| --- | --- |
| **OK** | Validates the settings, saves them, and closes the dialog. The endpoint, API key, and model must all be filled in. If embedding settings were changed, a confirmation prompt warns that existing vector stores may need rebuilding, and a second message recommends rebuilding the schema library. |
| **Cancel** | Discards changes and closes the dialog. Any in-progress connection test is cancelled. |
| **Test Connection** | Sends a minimal probe request to verify the LLM endpoint, API key, and model. If embedding settings are configured, it also tests the embedding endpoint. Times out after 30 seconds. |
| **Help** | Opens this documentation page in your default browser. |

The dialog has no tabs: it groups its settings into **LLM Settings**, **Embedding Settings (Vector Search)**, **Precomputed Query Routing**, **Semantic Options**, and **AI Data Analysis**, with the status bar at the bottom.

## LLM Settings

This group configures the large language model used for chat completions, SQL generation, question generation, and other text-generation tasks.

| Field | Description |
| --- | --- |
| **Endpoint** | URL of the chat completions API. Select from the drop-down list of suggested endpoints or type a custom URL. The list adapts to your system locale — Chinese-language systems see additional China-based providers (DeepSeek, Moonshot, DashScope, Qianfan, Volcengine, MiniMax) listed first. The endpoint is normalized automatically (for example, redundant `/v1` segments in Google Gemini URLs are stripped). |
| **API Key** | Secret key for authenticating with the LLM provider. Characters are masked by default; use the check box beside the field (tooltip **Show / hide API key**) to toggle visibility. A key is not required for local Ollama endpoints when you click **Test Connection** or refresh the model list, but **OK** requires one. |
| **Model** | The completion model to call. The drop-down updates automatically when you change the endpoint to show models appropriate for that provider. Click the **Refresh** button (⟳) next to the combo box to fetch the current list of available models from the provider's models API. You can also type any model name directly. |

### Supported LLM providers and suggested models

The dialog recognizes the following providers by endpoint URL and pre-populates the model list accordingly:

| Provider | Endpoint pattern | Suggested models |
| --- | --- | --- |
| OpenAI | `api.openai.com` | gpt-4o, gpt-4o-mini, o1, o3-mini, o1-mini |
| Anthropic | `api.anthropic.com` | claude-3-7-sonnet-20250219, claude-3-5-sonnet-20241022, claude-3-opus-20240229, claude-3-5-haiku-20241022 |
| Google Gemini | `generativelanguage.googleapis.com` | gemini-2.5-flash, gemini-2.0-flash, gemini-1.5-pro, gemini-1.5-flash |
| xAI (Grok) | `api.x.ai` | grok-2-latest, grok-2-vision-latest |
| Azure OpenAI | `.openai.azure.com` | my-gpt-4o (deployment name) |
| Mistral | `api.mistral.ai` | mistral-large-latest, pixtral-large-latest, mistral-small-latest, open-mistral-nemo |
| Cohere | `api.cohere.ai` | command-r-plus-08-2024, command-r-plus, command-r-08-2024, command-r |
| DeepSeek | `api.deepseek.com` | deepseek-chat, deepseek-reasoner |
| Moonshot | `api.moonshot.cn` | moonshot-v1-8k, moonshot-v1-32k, moonshot-v1-128k |
| Alibaba DashScope | `dashscope.aliyuncs.com` | qwen-max, qwen-plus, qwen-turbo, qwen-vl-max |
| Baidu Qianfan | `qianfan.baidubce.com` | ernie-4.0-8k-latest, ernie-4.0-turbo-8k-latest, ernie-3.5-8k, ernie-speed-128k |
| Volcengine (Ark) | `volces.com` | ep-2024xxxx-xxxxx |
| MiniMax | `api.minimax.io` | abab6.5s-chat, abab6.5g-chat, abab6.5t-chat |
| Ollama (local) | `localhost:11434` | No list is pre-populated; click **Refresh** to load the models from the local `/api/tags` endpoint. |

For unrecognized endpoints, a general list of popular models is shown (gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-4, gpt-3.5-turbo, gpt-4.1, gpt-4.1-mini, o1, o3-mini, grok-3, grok-3-mini, grok-2, gemini-2.5-pro-preview-05-06, gemini-2.0-flash, gemini-1.5-pro).

### Model refresh

Clicking the **Refresh** button queries the provider's models listing API:

- **Google Gemini**: `GET /v1beta/models?key=...` (API key passed as query parameter).
- **Azure OpenAI**: `GET /openai/models?api-version=2024-10-21`.
- **Ollama**: `GET /api/tags`.
- **OpenAI-compatible** providers: `GET /{version}/models`, where `{version}` is the version segment found in the endpoint path (defaulting to `v1`). Endpoints that use a `/compatible-mode/` path (for example Alibaba DashScope) list the models of that path instead.

The previously selected model is preserved if it still appears in the refreshed list; otherwise the first model in the list is selected. The status bar reports how many models were loaded, or why the refresh failed.

### Test connection behavior

When you click **Test Connection**, the dialog:

1. Validates that the endpoint and API key are provided (API key is optional for local Ollama endpoints).
2. Sends a minimal chat completion request (max 5 tokens) to verify the LLM endpoint, key, and model. For **Google Gemini**, a lightweight `GET /v1beta/models` probe is used instead to avoid consuming tokens and hitting rate limits. If a model name is specified, it verifies the model appears in the returned list.
3. For **Azure OpenAI**, appends `?api-version=2024-02-01` if no `api-version` parameter is present.
4. If the initial request fails but the model exists in the provider's model list, the test still passes (some models return errors for truncated requests but are otherwise valid). A model that the provider reports as served only by `v1/responses` and not by `v1/chat/completions` is treated as a failure.
5. If embedding settings are configured (endpoint + API key), sends a minimal embedding request with the input "test" to verify the embedding endpoint. When no embedding endpoint and key are configured, the status bar reports that the embedding test was skipped.
6. Reports success or failure in the status bar at the bottom of the dialog. Double-click the status bar to copy its text to the clipboard.

## Embedding Settings (Vector Search)

This group configures the embedding model used when the application builds or queries vector indexes for semantic search over schema documentation and knowledge base content.

| Field | Description |
| --- | --- |
| **Endpoint** | Base URL for the embeddings API. When left blank, the application derives it from the LLM chat endpoint by replacing `/chat/completions` with `/embeddings`. For Azure OpenAI, the same substitution is applied and `api-version` is appended if missing. |
| **API Key** | API key for embedding requests. When left blank, the main LLM API key is used. Characters are masked by default; use the check box beside the field (tooltip **Show / hide embedding API key**) to toggle visibility. |
| **Model** | Embedding model name, selected from the drop-down (`text-embedding-ada-002`, `text-embedding-3-small`, `text-embedding-3-large`) or typed manually. Required for standard OpenAI; ignored for Azure deployments (where the deployment name in the endpoint URL determines the model). |

> **Note:** Changing embedding settings may invalidate existing vector indexes. When you click **OK** after modifying embedding settings, the dialog prompts you to confirm and then recommends rebuilding the schema library.

## Precomputed Query Routing

This group controls similarity thresholds for matching incoming natural-language questions against previously reviewed SQL queries stored in the knowledge base, the threshold used when matching discovered objects and columns, plus BM25 lexical retrieval tuning.

| Field | Range | Default | Description |
| --- | --- | --- | --- |
| **Direct match threshold** | 0.00 – 1.00 | 0.93 | Minimum cosine similarity score for returning a precomputed SQL result directly without calling the LLM. Higher values require a closer match. |
| **Related match threshold** | 0.00 – 1.00 | 0.82 | Minimum cosine similarity score for injecting a precomputed SQL as few-shot context into the LLM prompt. Lower than the direct threshold so related examples are included even when an exact match is not found. |
| **Object search vector threshold** | 0.00 – 1.00 | 0.50 | Maximum vector similarity threshold accepted for object and column discovery matches. |
| **Enable BM25 retrieval** | On / Off | Off | Enables lexical BM25 ranking as an additional discovery signal alongside vector similarity. |
| **BM25 Weight** | 0.00 – 5.00 | 0.50 | Reciprocal Rank Fusion (RRF) weight applied to BM25-ranked results when combining with vector search scores. |
| **BM25 k1** | 0.05 – 5.00 | 1.20 | BM25 term-frequency saturation parameter. Higher values increase the influence of term frequency. |
| **BM25 b** | 0.00 – 1.00 | 0.75 | BM25 document-length normalization parameter. 0 disables length normalization; 1 fully normalizes. |

## Semantic Options

| Field | Description |
| --- | --- |
| **Allow semantic compile fallback to raw SQL** | When enabled, semantic mode falls back to executing raw SQL if SMQ parsing or compilation against the active semantic model fails. When disabled, compilation failures surface as errors instead of silently reverting. This is a global setting that applies to all data sources. |

## AI Data Analysis

| Field | Description |
| --- | --- |
| **Allowing AI to analyze real data** | When enabled, the data shown in the data preview can be sent to the configured LLM provider for analysis. This option is off by default. Turning it on shows a consent prompt that explains that the previewed data leaves your machine and is processed by your LLM provider; if you do not agree, the option stays off. |

## Status bar

The status bar at the bottom of the dialog displays validation messages, connection test progress, and error details. It reports states such as "Testing connection...", "Testing LLM connection...", "LLM OK. Testing embedding connection...", "LLM and embedding connections successful.", and "LLM connection successful. (Embedding not configured — skipped.)". Required-field problems ("Endpoint is required.", "API key is required.", "Model name is required.") and failures ("Test timed out.", "Connection failed: ...") are shown there as well. Error messages appear in red. **Double-click** the status bar to copy its contents to the clipboard (useful for reporting issues).

## Related topics

- [Application Options Dialog](application-options-dialog.md) — analysis limits, NULL/blank handling, connection timeout, and other application-wide options.
- [Schema Library Form](schema-library-form.md) — managing semantic models and vector indexes that depend on the embedding settings configured here.
- [AI Agent Manager Window](ai-agent-manager-window.md) — per-agent configuration including semantic layer enablement.

[Back to Windows and Elements](windows-and-elements.md)

## Screenshot

![AI Provider Settings](images/AI_Provider_Settings.png)
