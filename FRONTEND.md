# Frontend Documentation

> React + TypeScript chat interface with admin panel for the Octofy AI Agent.

---

## Overview

The frontend provides a conversational interface for natural language to SQL generation, plus an admin panel for managing schemas, knowledge base, and value index.

---

## Technology Stack

| Technology | Purpose |
|------------|---------|
| **React 18** | UI framework |
| **TypeScript** | Type safety |
| **Vite** | Build tool and dev server |
| **TailwindCSS** | Styling |
| **Axios** | HTTP client |
| **Recharts** | Data visualization |
| **React Markdown** | Markdown rendering |

---

## Project Structure

```
frontend/
├── src/
│   ├── api/
│   │   └── client.ts           # API client with axios interceptors
│   ├── components/
│   │   ├── Charts/             # Chart components (Bar, Line, Pie, etc.)
│   │   ├── DataTable/          # Data table with pagination
│   │   ├── Sidebar/            # Conversation sidebar
│   │   ├── SQL/                # SQL result display
│   │   ├── DataProfileCard.tsx # Data profiling display
│   │   ├── ErrorBoundary.tsx   # Error handling
│   │   ├── InsightsPanel.tsx   # AI insights display
│   │   ├── Pagination.tsx      # Pagination component
│   │   ├── RefinementSuggestions.tsx # Query refinement suggestions
│   │   └── Toast.tsx           # Toast notifications
│   ├── pages/
│   │   └── Admin/
│   │       ├── AdminLayout.tsx      # Admin page layout
│   │       ├── SchemaManager.tsx    # Schema management
│   │       ├── FewShotManager.tsx   # Knowledge base management
│   │       ├── ValueManager.tsx     # Value index management
│   │       ├── ContributionManager.tsx # Contribution review
│   │       └── Settings.tsx         # System settings
│   ├── types/
│   │   └── conversation.ts     # TypeScript interfaces
│   ├── utils/
│   │   ├── conversationStorage.ts  # localStorage persistence
│   │   └── chartIntentDetector.ts  # Chart type detection
│   └── App.tsx                 # Main application component
├── vite.config.ts              # Vite configuration
├── tailwind.config.js          # TailwindCSS configuration
└── package.json
```

---

## Key Components

### App.tsx - Main Application

The main component handles:
- **Multi-conversation management**: Create, delete, rename, switch conversations
- **Query modes**: SQL, R, SAS, Python generation, and object search
- **Streaming responses**: SSE-based real-time status updates
- **Chart type detection**: Natural language chart requests (e.g., "show as pie chart")
- **Clarification flow**: Handles uncertain query classification

### Chat Interface

```typescript
interface ChatMessage {
  id: string;
  type: 'user' | 'ai';
  content: string;
  timestamp: Date;
  discoveryResult?: DiscoveryResponse;
  sqlResult?: GenerateSQLResponse;
  queryType?: 'database' | 'general' | 'uncertain' | 'search' | 'r_code' | 'sas_code' | 'python_code';
  executionResult?: ExecutePythonResponse;
  chartTypeOverride?: ChartTypeOption;
  analysisContext?: AnalysisContext;
}

interface Conversation {
  id: string;
  title: string;
  lastModified: string;
  messages: ChatMessage[];
  lastGeneratedSQL?: string;
  queryHistory?: string;
  selectedObjects?: string[];
}
```

### Query Modes

| Mode | Description | API Endpoint |
|------|-------------|--------------|
| **Generate SQL** | Natural language to T-SQL | `/api/v1/generate-sql` |
| **Generate R** | Natural language to R code | `/api/v1/generate-r` |
| **Generate SAS** | Natural language to SAS code | `/api/v1/generate-sas` |
| **Generate Python** | Natural language to Python code | `/api/v1/generate-python` |
| **Search Objects** | Find database tables/views | `/api/v1/generate-sql` (search mode) |

---

## API Client

### Configuration

The API client uses localStorage for configuration with fallbacks:

```typescript
const getApiBaseUrl = () => {
    return localStorage.getItem('api_base_url') || '/api/v1';
};

const getApiKey = () => {
    return localStorage.getItem('api_key') || '***REMOVED***';
};
```

### Key Methods

```typescript
const api = {
    // Discovery
    discovery(query: string): Promise<DiscoveryResponse>
    
    // SQL Generation (non-streaming)
    generateSQL(query, context?, previousSQL?, queryHistory?, forceGeneral?, queryMode?, tableOverride?): Promise<GenerateSQLResponse>
    
    // SQL Generation (streaming SSE)
    generateSQLStream(query, onStatus, context?, previousSQL?, queryHistory?, forceGeneral?, queryMode?, signal?, tableOverride?): Promise<GenerateSQLResponse>
    
    // Code Generation (streaming)
    generateRStream(query, onStatus, context?, signal?): Promise<GenerateSQLResponse>
    generateSASStream(query, onStatus, context?, signal?): Promise<GenerateSQLResponse>
    generatePythonStream(query, onStatus, context?, signal?): Promise<GenerateSQLResponse>
    
    // Python Execution
    executePython(code, context?, chartTypeOverride?): Promise<ExecutePythonResponse>
    
    // Admin operations
    getSchemaStatus(): Promise<AdminSchemaStatus[]>
    syncSchema(schema, table): Promise<void>
    getFewShots(): Promise<FewShotItem[]>
    // ... more admin methods
}
```

---

## Admin Pages

### Schema Manager

Manages database table schemas in the vector store:
- View all schemas with sync status
- Sync individual tables or all schemas
- Bulk import/export via Excel
- Edit table descriptions
- Delete schemas from index

### Few-Shot Manager (Knowledge Base)

Manages query examples for LLM context:
- Add/edit/delete examples
- Bulk import/export via Excel
- Supports SQL, R, and SAS examples
- Verification status tracking

### Value Manager

Manages the value index for categorical lookups:
- Search indexed values
- Bulk import via Excel/CSV
- Clear and rebuild index
- Export current index

### Contribution Manager

Reviews user-submitted examples:
- View pending contributions
- Approve (moves to knowledge base)
- Reject (deletes contribution)
- Edit before approval

### Settings

System configuration:
- Database connection settings
- LLM configuration (model, endpoint, API key)
- Embedding configuration
- Vector store settings
- Connection testing

---

## Data Visualization

### Supported Chart Types

```typescript
type ChartTypeOption = 
  | 'bar' | 'line' | 'pie' | 'scatter' | 'column'
  | 'stackedBar' | 'stackedColumn' | 'clusteredColumn'
  | 'area' | 'radar' | 'treemap' | 'funnel' | 'none';
```

### Chart Intent Detection

The frontend detects chart requests from natural language:

```typescript
// Examples that trigger chart type detection:
"show as pie chart"
"display as line graph"
"make it a bar chart"
"visualize as scatter plot"
```

### Visualization Config

```typescript
interface VizConfig {
  category: '2d_data' | '3d_data' | 'no_chart' | 'too_much_data';
  allowed_charts: string[];
  message: string;
}
```

---

## Workflow Analysis

### Data Profiling

Automatic data profiling on query execution:

```typescript
interface DataProfile {
  row_count: number;
  column_count: number;
  columns: ColumnProfile[];
  correlations?: Array<{ col1, col2, correlation }>;
  has_datetime: boolean;
  datetime_columns: string[];
  profiling_level: 'basic' | 'distribution' | 'relationship';
}
```

### Insights

AI-generated insights from data:

```typescript
interface Insight {
  insight_type: 'outlier' | 'trend' | 'correlation' | 'missing_data' | 'distribution' | 'recommendation';
  title: string;
  description: string;
  severity: 'info' | 'warning' | 'critical';
  related_columns: string[];
  confidence: number;
}
```

### Refinement Suggestions

Suggested follow-up queries based on results:

```typescript
interface AnalysisContext {
  data_profile?: DataProfile;
  insights: Insight[];
  refinement_history: Array<{ intent, query, timestamp }>;
  suggested_refinements: string[];
}
```

---

## State Management

### Conversation Storage

Conversations are persisted to localStorage:

```typescript
const conversationStorage = {
  loadConversations(): Conversation[]
  saveConversations(conversations: Conversation[]): void
  loadActiveConversationId(): string | null
  saveActiveConversationId(id: string): void
}
```

### Auto-Titling

Conversations are auto-titled based on content:
- Initial title from first user query (truncated)
- Auto-generated title after 2 exchanges using LLM

---

## Development

### Running Locally

```bash
cd frontend
npm install
npm run dev
```

The dev server runs on **http://localhost:45678** with proxy to backend.

### Vite Configuration

```typescript
// vite.config.ts
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 45678,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  }
})
```

### Testing

```bash
npm run test        # Run tests
npm run test:watch  # Watch mode
```

### Building

```bash
npm run build       # Production build
npm run preview     # Preview production build
```

---

## Styling

### TailwindCSS Theme

The app uses a dark theme with slate/indigo color palette:

```javascript
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        // Custom colors defined here
      }
    }
  }
}
```

### Key CSS Classes

| Class Pattern | Usage |
|---------------|-------|
| `bg-slate-900` | Primary background |
| `text-slate-200` | Primary text |
| `border-slate-800` | Borders |
| `text-indigo-400` | Accent text |
| `bg-indigo-600` | Primary buttons |
| `text-emerald-400` | Success states |

---

## Error Handling

### ErrorBoundary

Wraps the app to catch React errors:

```tsx
<ErrorBoundary>
  <App />
</ErrorBoundary>
```

### Toast Notifications

Non-blocking notifications for user feedback:

```tsx
<Toast
  message="Schema synced successfully"
  type="success"  // 'success' | 'error' | 'info' | 'warning'
  onClose={() => setToast(null)}
/>
```

### API Error Handling

```typescript
try {
  const result = await api.generateSQLStream(...);
} catch (error) {
  if (error.name === 'AbortError') {
    // User cancelled
  } else if (error.response?.data?.detail) {
    // Server error with detail
  } else {
    // Generic error
  }
}
```
