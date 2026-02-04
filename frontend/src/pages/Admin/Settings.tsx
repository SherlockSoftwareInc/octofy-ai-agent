import { useState, useEffect } from 'react';
import { Cpu, Network, Info, Loader2, CheckCircle, AlertCircle, Save } from 'lucide-react';
import { api } from '../../api/client';
import type { AgentSettings } from '../../api/client';

const getErrorDetail = (error: unknown, fallback: string) => {
  const err = error as { response?: { data?: { detail?: string; message?: string } }; message?: string };
  return err.response?.data?.detail || err.response?.data?.message || err.message || fallback;
};

export const Settings = () => {
  const [settings, setSettings] = useState<AgentSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [models, setModels] = useState<{ id: string; name: string }[]>([]);
  const [saveStatus, setSaveStatus] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const [errorString, setErrorString] = useState<string | null>(null);

  // LLM Fetch state
  const [fetchingModels, setFetchingModels] = useState(false);
  const [fetchModelError, setFetchModelError] = useState<string | null>(null);
  const [manualModelEntry, setManualModelEntry] = useState(false);


  // Removed API Client Configuration - users now authenticate with their own API keys

  useEffect(() => {
    initializeSettings();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const initializeSettings = async () => {
    setLoading(true);
    try {
      // User is already authenticated with their own API key
      // Just load settings and models directly
      await Promise.all([loadSettings(), loadModels()]);
    } catch (error) {
      console.error('Failed to initialize settings', error);
    } finally {
      setLoading(false);
    }
  };

  const loadSettings = async () => {
    try {
      setErrorString(null);
      const data = await api.admin.getSettings();
      setSettings(data);
    } catch (error) {
      console.error('Failed to load settings', error);
      setErrorString(getErrorDetail(error, 'Unknown error'));
    } finally {
      setLoading(false);
    }
  };

  const loadModels = async () => {
    try {
      const data = await api.admin.getModels();
      setModels(data.models || []);
    } catch (error) {
      console.error('Failed to load models', error);
      // Models failure is non-critical for settings page load, but we log it.
    }
  };

  const handleFetchModels = async () => {
    if (!settings) return;

    setFetchingModels(true);
    setFetchModelError(null);
    try {
      const endpoint = settings.llm_config.llm_endpoint;
      const apiKey = settings.llm_config.llm_api_key;

      if (!endpoint) {
        setFetchModelError("Please enter an endpoint URL first.");
        return;
      }

      const data = await api.admin.fetchModels(endpoint, apiKey);
      setModels(data.models || []);

      if (data.models && data.models.length > 0) {
        // Auto-select first model if current is not in list
        const currentModel = settings.llm_config.llm_model;
        if (!data.models.find((m: { id: string }) => m.id === currentModel)) {
          setSettings({ ...settings, llm_config: { ...settings.llm_config, llm_model: data.models[0].id } });
        }
      }

    } catch (error) {
      console.error('Failed to fetch models', error);
      setFetchModelError(getErrorDetail(error, 'Failed to fetch models from endpoint'));
      // Check if we should switch to manual entry
      if (settings?.llm_config.llm_endpoint) {
        setManualModelEntry(true);
      }
    } finally {
      setFetchingModels(false);
    }
  };

  const handleSave = async () => {
    if (!settings) return;

    setSaving(true);
    setSaveStatus(null);

    try {
      const savedSettings = await api.admin.updateSettings(settings);
      if (savedSettings) {
        setSettings(savedSettings);
        setSaveStatus({ type: 'success', message: 'Settings saved! Verifying configuration...' });

        // Perform verification after save (LLM and Milvus only)
        try {
          const verifyResult = await api.admin.verifySettings();

          if (verifyResult.llm_connected && verifyResult.milvus_connected) {
            setSaveStatus({
              type: 'success',
              message: 'Settings saved and verified! LLM and Vector Store (Milvus) are successfully connected.'
            });
          } else {
            const errors: string[] = [];
            if (!verifyResult.llm_connected) errors.push(`[LLM: ${verifyResult.llm_message}]`);
            if (!verifyResult.milvus_connected) errors.push(`[Milvus: ${verifyResult.milvus_message}]`);

            setSaveStatus({
              type: 'error',
              message: `Settings saved but verification failed. ${errors.join(' ')}`
            });
          }
        } catch (verifyError) {
          console.error('Verification failed', verifyError);
          setSaveStatus({
            type: 'error',
            message: 'Settings saved, but failed to perform verification check.'
          });
        }
      } else {
        console.error('Invalid response from server:', savedSettings);
        setSaveStatus({ type: 'error', message: 'Saved, but received invalid response from server.' });
      }
    } catch (error) {
      setSaveStatus({ type: 'error', message: getErrorDetail(error, 'Failed to save settings') });
    } finally {
      setSaving(false);
    }
  };

  // Removed legacy API configuration handlers - users authenticate with their own API keys

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="animate-spin text-indigo-400" size={32} />
      </div>
    );
  }

  if (!settings) {
    return (
      <div className="flex flex-col items-center justify-center h-full space-y-4">
        <AlertCircle className="text-red-400" size={48} />
        <h3 className="text-xl font-semibold text-slate-200">Failed to load settings</h3>
        <p className="text-slate-400 max-w-md text-center">
          We couldn't reach the backend server. This is often caused by a misconfigured API URL in your browser settings.
        </p>

        {errorString && (
          <div className="p-4 bg-red-900/20 border border-red-500/30 rounded-lg max-w-lg text-center font-mono text-sm text-red-300">
            {errorString}
          </div>
        )}

        <div className="flex gap-4 mt-2">
        <button
          onClick={() => { setLoading(true); loadSettings(); }}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg flex items-center gap-2 transition-colors"
        >
          <Loader2 size={16} className={loading ? "animate-spin" : "hidden"} />
          Retry Connection
        </button>
      </div>
      </div>
    );
  }

  return (
    <div className="p-6 w-full h-full space-y-6 overflow-y-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold bg-gradient-to-r from-indigo-400 to-cyan-400 bg-clip-text text-transparent">Agent Settings</h2>
          <p className="text-slate-400 text-sm mt-1">Configure your Octofy AI Agent application</p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saving ? <Loader2 className="animate-spin" size={16} /> : <Save size={16} />}
          {saving ? 'Saving...' : 'Save Settings'}
        </button>
      </div>

      {saveStatus && (
        <div className={`p-4 rounded-lg flex items-start gap-3 ${saveStatus.type === 'success' ? 'bg-green-500/10 border border-green-500/30' : 'bg-red-500/10 border border-red-500/30'}`}>
          {saveStatus.type === 'success' ? <CheckCircle className="text-green-400" size={20} /> : <AlertCircle className="text-red-400" size={20} />}
          <p className={`${saveStatus.type === 'success' ? 'text-green-300' : 'text-red-300'}`}>{saveStatus.message}</p>
        </div>
      )}

      {/* LLM Configuration Card */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6">
        <div className="flex items-center gap-3 mb-4">
          <Cpu className="text-purple-400" size={20} />
          <h3 className="text-lg font-semibold text-white">LLM Configuration</h3>
        </div>
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="llm-endpoint" className="block text-sm text-slate-400 mb-2">Endpoint URL (OpenAI Compatible)</label>
              <input
                id="llm-endpoint"
                type="text"
                value={settings.llm_config.llm_endpoint || ''}
                onChange={(e) => setSettings({ ...settings, llm_config: { ...settings.llm_config, llm_endpoint: e.target.value } })}
                className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="https://api.openai.com/v1"
              />
            </div>
            <div>
              <label htmlFor="llm-api-key" className="block text-sm text-slate-400 mb-2">API Key (Optional)</label>
              <input
                id="llm-api-key"
                type="password"
                value={settings.llm_config.llm_api_key || ''}
                onChange={(e) => setSettings({ ...settings, llm_config: { ...settings.llm_config, llm_api_key: e.target.value } })}
                className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="sk-..."
              />
              <p className="text-xs text-slate-500 mt-1">Leave empty to use OPENAI_API_KEY from environment</p>
            </div>
          </div>

          <div className="flex items-end gap-2">
            <div className="flex-1">
              <div className="flex justify-between items-center mb-2">
                <label htmlFor="llm-model" className="block text-sm text-slate-400">Model</label>
                <button
                  onClick={() => setManualModelEntry(!manualModelEntry)}
                  className="text-xs text-indigo-400 hover:text-indigo-300 underline"
                  type="button"
                >
                  {manualModelEntry ? "Select from list" : "Enter manually"}
                </button>
              </div>
              {manualModelEntry ? (
                <input
                  id="llm-model"
                  type="text"
                  value={settings.llm_config.llm_model}
                  onChange={(e) => setSettings({ ...settings, llm_config: { ...settings.llm_config, llm_model: e.target.value } })}
                  className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  placeholder="e.g. gpt-4o"
                />
              ) : (
                <select
                  id="llm-model"
                  value={settings.llm_config.llm_model}
                  onChange={(e) => setSettings({ ...settings, llm_config: { ...settings.llm_config, llm_model: e.target.value } })}
                  className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  aria-label="Select LLM Model"
                >
                  {/* Always show current option if not in list to prevent it from disappearing */}
                  {!models.find(m => m.id === settings.llm_config.llm_model) && (
                    <option value={settings.llm_config.llm_model}>{settings.llm_config.llm_model}</option>
                  )}
                  {models.map(model => (
                    <option key={model.id} value={model.id}>{model.name}</option>
                  ))}
                </select>
              )}
            </div>
            <button
              onClick={handleFetchModels}
              disabled={fetchingModels || !settings.llm_config.llm_endpoint}
              className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed mb-[1px]"
              title="Fetch models from endpoint"
            >
              {fetchingModels ? <Loader2 className="animate-spin" size={20} /> : "Fetch Models"}
            </button>
          </div>

          {fetchModelError && (
            <p className="text-sm text-red-400">{fetchModelError}</p>
          )}

          <div>
            <label htmlFor="llm-temperature" className="block text-sm text-slate-400 mb-2">
              Temperature: {settings.llm_config.temperature.toFixed(1)}
            </label>
            <input
              id="llm-temperature"
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={settings.llm_config.temperature}
              onChange={(e) => setSettings({ ...settings, llm_config: { ...settings.llm_config, temperature: parseFloat(e.target.value) } })}
              className="w-full"
              aria-label="LLM Temperature"
            />
            <div className="flex justify-between text-xs text-slate-500 mt-1">
              <span>Deterministic (0.0)</span>
              <span>Creative (1.0)</span>
            </div>
          </div>
        </div>
      </div>

      {/* Vector Store & Embedding Configuration Card */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6">
        <div className="flex items-center gap-3 mb-4">
          <Network className="text-cyan-400" size={20} />
          <h3 className="text-lg font-semibold text-white">Vector Store & Embedding Configuration</h3>
        </div>

        {/* Warning */}
        <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-lg mb-6">
          <div className="flex items-start gap-2">
            <AlertCircle className="text-amber-400 shrink-0 mt-0.5" size={16} />
            <div className="text-sm text-amber-300">
              <p className="font-semibold mb-1">Important: Configuration Changes</p>
              <p className="opacity-90 leading-relaxed">
                Changing embedding or vector store settings (Provider, Model, Dimensions) will impact existing vectors.
                You MUST <strong>re-index your documents</strong> (Schema & Few-Shot) after saving changes to ensure compatibility.
              </p>
            </div>
          </div>
        </div>

        <div className="space-y-6">
          {/* Embedding Section */}
          <div className="space-y-4">
            <h4 className="text-sm font-medium text-slate-300 uppercase tracking-wider border-b border-slate-800 pb-2">Embedding Settings</h4>
            <div>
              <label htmlFor="embedding-provider" className="block text-sm text-slate-400 mb-2">Embedding Provider</label>
              <select
                id="embedding-provider"
                value={settings.embedding_config?.provider || 'openai'}
                onChange={(e) => setSettings({ ...settings, embedding_config: { ...settings.embedding_config, provider: e.target.value } })}
                className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                aria-label="Select Embedding Provider"
              >
                <option value="openai">OpenAI</option>
                <option value="azure">Azure OpenAI</option>
                <option value="openai_compatible">OpenAI Compatible (Custom)</option>
                <option value="huggingface">HuggingFace (Local)</option>
              </select>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label htmlFor="embedding-model" className="block text-sm text-slate-400 mb-2">Embedding Model</label>
                <input
                  id="embedding-model"
                  type="text"
                  value={settings.embedding_config?.model || ''}
                  onChange={(e) => setSettings({ ...settings, embedding_config: { ...settings.embedding_config, model: e.target.value } })}
                  className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  placeholder="e.g. text-embedding-3-small"
                />
              </div>
              <div>
                <label htmlFor="embedding-dimensions" className="block text-sm text-slate-400 mb-2">Dimensions</label>
                <input
                  id="embedding-dimensions"
                  type="number"
                  value={settings.embedding_config?.dimensions || 1536}
                  onChange={(e) => setSettings({ ...settings, embedding_config: { ...settings.embedding_config, dimensions: parseInt(e.target.value) } })}
                  className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            </div>

            {(settings.embedding_config?.provider === 'openai_compatible' || settings.embedding_config?.provider === 'azure') && (
              <div>
                <label htmlFor="embedding-base-url" className="block text-sm text-slate-400 mb-2">Base URL / Endpoint</label>
                <input
                  id="embedding-base-url"
                  type="text"
                  value={settings.embedding_config?.base_url || ''}
                  onChange={(e) => setSettings({ ...settings, embedding_config: { ...settings.embedding_config, base_url: e.target.value } })}
                  className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  placeholder="https://..."
                />
              </div>
            )}

            <div>
              <label htmlFor="embedding-api-key" className="block text-sm text-slate-400 mb-2">API Key</label>
              <input
                id="embedding-api-key"
                type="password"
                value={settings.embedding_config?.api_key || ''}
                onChange={(e) => setSettings({ ...settings, embedding_config: { ...settings.embedding_config, api_key: e.target.value } })}
                className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder={settings.embedding_config?.api_key ? "••••••••" : "Leave empty to use default"}
              />
            </div>
          </div>

          {/* Vector Store Section */}
          <div className="space-y-4">
            <h4 className="text-sm font-medium text-slate-300 uppercase tracking-wider border-b border-slate-800 pb-2">Vector Database Settings</h4>
            <div>
              <label htmlFor="vector-provider" className="block text-sm text-slate-400 mb-2">Vector Provider</label>
              <input
                id="vector-provider"
                type="text"
                value={settings.vector_config.provider}
                onChange={(e) => setSettings({ ...settings, vector_config: { ...settings.vector_config, provider: e.target.value } })}
                className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="vector-host" className="block text-sm text-slate-400 mb-2">Host</label>
                <input
                  id="vector-host"
                  type="text"
                  value={settings.vector_config.host}
                  onChange={(e) => setSettings({ ...settings, vector_config: { ...settings.vector_config, host: e.target.value } })}
                  className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <div>
                <label htmlFor="vector-port" className="block text-sm text-slate-400 mb-2">Port</label>
                <input
                  id="vector-port"
                  type="text"
                  value={settings.vector_config.port}
                  onChange={(e) => setSettings({ ...settings, vector_config: { ...settings.vector_config, port: e.target.value } })}
                  className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* App Metadata Card */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6">
        <div className="flex items-center gap-3 mb-4">
          <Info className="text-emerald-400" size={20} />
          <h3 className="text-lg font-semibold text-white">Application Metadata</h3>
        </div>
        <div className="space-y-4">
          <div>
            <label htmlFor="app-name" className="block text-sm text-slate-400 mb-2">Application Name</label>
            <input
              id="app-name"
              type="text"
              value={settings.app_meta.app_name}
              onChange={(e) => setSettings({ ...settings, app_meta: { ...settings.app_meta, app_name: e.target.value } })}
              className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label htmlFor="app-version" className="block text-sm text-slate-400 mb-2">Version</label>
            <input
              id="app-version"
              type="text"
              value={settings.app_meta.version}
              onChange={(e) => setSettings({ ...settings, app_meta: { ...settings.app_meta, version: e.target.value } })}
              className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label htmlFor="project-name" className="block text-sm text-slate-400 mb-2">Project Name</label>
            <input
              id="project-name"
              type="text"
              value={settings.app_meta.project_name}
              onChange={(e) => setSettings({ ...settings, app_meta: { ...settings.app_meta, project_name: e.target.value } })}
              className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>
      </div>
    </div >
  );
};
