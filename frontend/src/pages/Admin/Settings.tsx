import React, { useState, useEffect } from 'react';
import { Database, Cpu, Network, Info, Loader2, CheckCircle, AlertCircle, PencilLine, Save, Key } from 'lucide-react';
import { api } from '../../api/client';
import type { AgentSettings } from '../../api/client';

interface ConnectionDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (
    connStr: string,
    decryptedStr: string,
    payload: {
      driver: string;
      server: string;
      database: string;
      authType: AuthType;
      username?: string;
      trustServerCertificate: boolean;
    }
  ) => void;
  initialValues?: {
    driver?: string;
    server?: string;
    database?: string;
    authType?: AuthType;
    username?: string;
    password?: string;
    trustServerCertificate?: boolean;
  };
}

type AuthType =
  | 'sql'
  | 'windows'
  | 'ad_integrated'
  | 'ad_password'
  | 'ad_interactive'
  | 'ad_service_principal';

type AuthUIState = {
  showUsername: boolean;
  showPassword: boolean;
  usernameLabel: string;
  passwordLabel: string;
  usernameOptional: boolean;
};

const authOptions: { value: AuthType; label: string }[] = [
  { value: 'sql', label: 'SQL Server Authentication (Legacy/Standard)' },
  { value: 'windows', label: 'Windows Authentication (On-premise AD / Local)' },
  { value: 'ad_integrated', label: 'Active Directory Integrated (SSO)' },
  { value: 'ad_password', label: 'Active Directory Password' },
  { value: 'ad_interactive', label: 'Active Directory Interactive (MFA)' },
  { value: 'ad_service_principal', label: 'Active Directory Service Principal' }
];

const getErrorDetail = (error: unknown, fallback: string) => {
  const err = error as { response?: { data?: { detail?: string; message?: string } }; message?: string };
  return err.response?.data?.detail || err.response?.data?.message || err.message || fallback;
};

const getAuthUIState = (authType: AuthType): AuthUIState => {
  switch (authType) {
    case 'windows':
    case 'ad_integrated':
      return {
        showUsername: false,
        showPassword: false,
        usernameLabel: 'Username',
        passwordLabel: 'Password',
        usernameOptional: false
      };
    case 'ad_password':
      return {
        showUsername: true,
        showPassword: true,
        usernameLabel: 'User ID',
        passwordLabel: 'Password',
        usernameOptional: false
      };
    case 'ad_interactive':
      return {
        showUsername: true,
        showPassword: false,
        usernameLabel: 'User ID',
        passwordLabel: 'Password',
        usernameOptional: true
      };
    case 'ad_service_principal':
      return {
        showUsername: true,
        showPassword: true,
        usernameLabel: 'Client ID',
        passwordLabel: 'Secret',
        usernameOptional: false
      };
    case 'sql':
    default:
      return {
        showUsername: true,
        showPassword: true,
        usernameLabel: 'Username',
        passwordLabel: 'Password',
        usernameOptional: false
      };
  }
};


const ConnectionDialog: React.FC<ConnectionDialogProps> = ({ isOpen, onClose, onSave, initialValues }) => {
  const [driver, setDriver] = useState('ODBC Driver 17 for SQL Server');
  const [server, setServer] = useState('');
  const [database, setDatabase] = useState('');
  const [authType, setAuthType] = useState<AuthType>(initialValues?.authType || 'sql');
  const [authUI, setAuthUI] = useState<AuthUIState>(getAuthUIState(initialValues?.authType || 'sql'));

  // Always sync authType state with initialValues.authType when dialog opens or initialValues.authType changes
  useEffect(() => {
    if (isOpen) {
      setAuthType(initialValues?.authType || 'sql');
      setAuthUI(getAuthUIState(initialValues?.authType || 'sql'));
    }
  }, [isOpen, initialValues?.authType]);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [trustServerCertificate, setTrustServerCertificate] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  // When dialog opens, reset fields to initialValues (except authType, which is handled above)
  React.useEffect(() => {
    if (isOpen) {
      setDriver(initialValues?.driver || 'ODBC Driver 17 for SQL Server');
      setServer(initialValues?.server || '');
      setDatabase(initialValues?.database || '');
      setUsername(typeof initialValues?.username === 'string' ? initialValues.username : '');
      setPassword(typeof initialValues?.password === 'string' ? initialValues.password : '');
      setTrustServerCertificate(initialValues?.trustServerCertificate ?? false);
      setTestResult(null);
      setTesting(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  const UpdateUIState = (selectedIndex: number) => {
    const selectedAuth = authOptions[selectedIndex]?.value ?? 'sql';
    setAuthUI(getAuthUIState(selectedAuth));
  };

  const handleAuthChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const selectedIndex = event.target.selectedIndex;
    const selectedAuth = authOptions[selectedIndex]?.value ?? 'sql';
    setAuthType(selectedAuth);
    UpdateUIState(selectedIndex);
  };

  const getCredentialValidationError = (selectedAuth: AuthType) => {
    if (selectedAuth === 'ad_password' || selectedAuth === 'ad_service_principal') {
      if (!username.trim() || !password.trim()) {
        return 'Please enter both username and password for this authentication mode.';
      }
    }
    return null;
  };

  const shouldSendUsername = authType === 'sql' || authType === 'ad_password' || authType === 'ad_interactive' || authType === 'ad_service_principal';
  const shouldSendPassword = authType === 'sql' || authType === 'ad_password' || authType === 'ad_service_principal';
  const resolvedUsername = shouldSendUsername && username.trim() ? username : undefined;
  const resolvedPassword = shouldSendPassword && password.trim() ? password : undefined;

  const handleTestConnection = async () => {
    const validationError = getCredentialValidationError(authType);
    if (validationError) {
      setTestResult({ success: false, message: validationError });
      return;
    }

    setTesting(true);
    setTestResult(null);

    try {
      const response = await api.admin.testConnection({
        driver,
        server,
        database,
        auth_type: authType,
        username: resolvedUsername,
        password: resolvedPassword,
        trust_server_certificate: trustServerCertificate
      });

      setTestResult(response);
    } catch (error) {
      setTestResult({
        success: false,
        message: getErrorDetail(error, 'Connection test failed')
      });
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    const validationError = getCredentialValidationError(authType);
    if (validationError) {
      setTestResult({ success: false, message: validationError });
      return;
    }

    try {
      const response = await api.admin.buildConnectionString({
        driver,
        server,
        database,
        auth_type: authType,
        username: resolvedUsername,
        password: resolvedPassword,
        trust_server_certificate: trustServerCertificate
      });

      onSave(response.encrypted, response.connection_string_masked, {
        driver,
        server,
        database,
        authType,
        username: resolvedUsername,
        trustServerCertificate
      });
      onClose();
    } catch (error) {
      console.error('Failed to build connection string', error);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4">
      <div className="w-full max-w-2xl bg-slate-950 border border-slate-800 rounded-2xl shadow-2xl p-6 space-y-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xl font-semibold text-white">Change Database Connection</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-white">✕</button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm text-slate-300 mb-2">Driver</label>
            <input
              type="text"
              value={driver}
              onChange={(e) => setDriver(e.target.value)}
              className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="ODBC Driver 17 for SQL Server"
            />
          </div>

          <div>
            <label className="block text-sm text-slate-300 mb-2">Server</label>
            <input
              type="text"
              value={server}
              onChange={(e) => setServer(e.target.value)}
              className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="localhost or server.database.windows.net"
            />
          </div>

          <div>
            <label className="block text-sm text-slate-300 mb-2">Database</label>
            <input
              type="text"
              value={database}
              onChange={(e) => setDatabase(e.target.value)}
              className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="Your database name"
            />
          </div>

          <div>
            <label htmlFor="connection-auth" className="block text-sm text-slate-300 mb-2">Authentication</label>
            <select
              id="connection-auth"
              value={authType}
              onChange={handleAuthChange}
              className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              {authOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            {(authType === 'ad_integrated' || authType === 'ad_interactive') && (
              <p className="text-xs text-slate-500 mt-2">
                Note: Active Directory Integrated and Interactive require ADAL to be installed on the client machine.
              </p>
            )}
          </div>

          {authUI.showUsername && (
            <div>
              <label htmlFor="connection-username" className="block text-sm text-slate-300 mb-2">
                {authUI.usernameLabel}
                {authUI.usernameOptional && <span className="text-xs text-slate-500 ml-2">(Optional)</span>}
              </label>
              <input
                id="connection-username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder={authUI.usernameLabel}
              />
            </div>
          )}

          {authUI.showPassword && (
            <div>
              <label htmlFor="connection-password" className="block text-sm text-slate-300 mb-2">{authUI.passwordLabel}</label>
              <input
                id="connection-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder={authUI.passwordLabel}
              />
            </div>
          )}

          <div className="flex items-start gap-3">
            <input
              id="trust-server-certificate"
              type="checkbox"
              checked={trustServerCertificate}
              onChange={(e) => setTrustServerCertificate(e.target.checked)}
              className="mt-1 h-4 w-4 rounded border-slate-600 bg-slate-900 text-indigo-500 focus:ring-indigo-500"
            />
            <label htmlFor="trust-server-certificate" className="text-sm text-slate-300">
              Trust server certificate (use for self-signed or internal CA certificates)
            </label>
          </div>

          <button
            onClick={handleTestConnection}
            disabled={testing || !server || !database}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {testing ? <Loader2 className="animate-spin" size={16} /> : <Database size={16} />}
            {testing ? 'Testing...' : 'Test Connection'}
          </button>

          {testResult && (
            <div className={`p-4 rounded-lg flex items-start gap-3 ${testResult.success ? 'bg-green-500/10 border border-green-500/30' : 'bg-red-500/10 border border-red-500/30'}`}>
              {testResult.success ? <CheckCircle className="text-green-400" size={20} /> : <AlertCircle className="text-red-400" size={20} />}
              <div>
                <p className={`font-medium ${testResult.success ? 'text-green-300' : 'text-red-300'}`}>
                  {testResult.success ? 'Connection Successful' : 'Connection Failed'}
                </p>
                <p className={`text-sm ${testResult.success ? 'text-green-300/70' : 'text-red-300/70'}`}>
                  {testResult.message}
                </p>
              </div>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 pt-4">
          <button
            onClick={onClose}
            className="px-4 py-2 text-slate-300 hover:text-white bg-slate-800/80 border border-slate-700 rounded-lg"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={!testResult?.success}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Save size={16} />
            Save Connection
          </button>
        </div>
      </div>
    </div>
  );
};

export const Settings = () => {
  const [settings, setSettings] = useState<AgentSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showConnectionDialog, setShowConnectionDialog] = useState(false);
  const [models, setModels] = useState<{ id: string; name: string }[]>([]);
  const [saveStatus, setSaveStatus] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const [errorString, setErrorString] = useState<string | null>(null);

  // LLM Fetch state
  const [fetchingModels, setFetchingModels] = useState(false);
  const [fetchModelError, setFetchModelError] = useState<string | null>(null);
  const [manualModelEntry, setManualModelEntry] = useState(false);


  // API Client Configuration state
  const [apiBaseUrl, setApiBaseUrl] = useState(localStorage.getItem('api_base_url') || '/api/v1');
  const [apiKey, setApiKey] = useState(localStorage.getItem('api_key') || 'dev-api-key-12345');

  useEffect(() => {
    loadSettings();
    loadModels();
  }, []);

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
      if (savedSettings && savedSettings.target_db) {
        setSettings(savedSettings);
        setSaveStatus({ type: 'success', message: 'Settings saved! Verifying configuration...' });

        // Perform verification after save
        try {
          const verifyResult = await api.admin.verifySettings();

          if (verifyResult.db_connected && verifyResult.llm_connected && verifyResult.milvus_connected) {
            setSaveStatus({
              type: 'success',
              message: 'Settings saved and verified! Database, LLM, and Vector Store (Milvus) are successfully connected.'
            });
          } else {
            const errors: string[] = [];
            if (!verifyResult.db_connected) errors.push(`[Database: ${verifyResult.db_message}]`);
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

  const handleConnectionSave = async (
    encrypted: string,
    decrypted: string,
    payload: {
      driver: string;
      server: string;
      database: string;
      authType: AuthType;
      username?: string;
      trustServerCertificate: boolean;
    }
  ) => {
    if (!settings) return;

    const {
      driver,
      server,
      database,
      authType,
      username,
      trustServerCertificate
    } = payload;

    const updatedSettings = {
      ...settings,
      target_db: {
        ...settings.target_db,
        connection_string_encrypted: encrypted,
        connection_string_decrypted: decrypted,
        driver: driver,
        auth_type: authType,
        username: username,
        trust_server_certificate: trustServerCertificate,
        server: server,
        database_name: database
      }
    };

    setSettings(updatedSettings);

    // Persist immediately to backend
    setSaving(true);
    setSaveStatus(null);
    try {
      const savedSettings = await api.admin.updateSettings(updatedSettings);
      if (savedSettings && savedSettings.target_db) {
        setSettings(savedSettings);
        setSaveStatus({ type: 'success', message: 'Connection settings saved successfully!' });
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

  const handleSaveApiConfig = () => {
    localStorage.setItem('api_base_url', apiBaseUrl);
    localStorage.setItem('api_key', apiKey);
    setSaveStatus({ type: 'success', message: 'API configuration saved! Please refresh the page for changes to take effect.' });

    // Clear the message after 5 seconds
    setTimeout(() => setSaveStatus(null), 5000);
  };

  const handleResetConfig = () => {
    localStorage.removeItem('api_base_url');
    localStorage.removeItem('api_key');
    window.location.reload();
  };



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

          <button
            onClick={handleResetConfig}
            className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg flex items-center gap-2 transition-colors"
          >
            <Database size={16} />
            Reset to Defaults
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
          <p className="text-slate-400 text-sm mt-1">Configure your SQL Agent application</p>
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

      {/* Target Database Card */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6">
        <div className="flex items-center gap-3 mb-4">
          <Database className="text-indigo-400" size={20} />
          <h3 className="text-lg font-semibold text-white">Target Database</h3>
        </div>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-slate-400 mb-2">Friendly Name</label>
            <input
              type="text"
              value={settings.target_db.friendly_name}
              onChange={(e) => setSettings({ ...settings, target_db: { ...settings.target_db, friendly_name: e.target.value } })}
              className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-2">Description</label>
            <textarea
              value={settings.target_db.description}
              onChange={(e) => setSettings({ ...settings, target_db: { ...settings.target_db, description: e.target.value } })}
              rows={2}
              className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-2">Keywords (comma-separated)</label>
            <input
              type="text"
              value={settings.target_db.keywords.join(', ')}
              onChange={(e) => setSettings({ ...settings, target_db: { ...settings.target_db, keywords: e.target.value.split(',').map(k => k.trim()).filter(k => k) } })}
              className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="sales, customers, orders"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-slate-400 mb-2">Server (read-only)</label>
              <input
                type="text"
                value={settings.target_db.server || 'Not configured'}
                className="w-full px-4 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-slate-400 cursor-not-allowed"
                disabled
              />
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-2">Database (read-only)</label>
              <input
                type="text"
                value={settings.target_db.database_name || 'Not configured'}
                className="w-full px-4 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-slate-400 cursor-not-allowed"
                disabled
              />
            </div>
          </div>



          <button
            onClick={() => setShowConnectionDialog(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg"
          >
            <PencilLine size={16} />
            Change Database Connection
          </button>
        </div>
      </div>

      {/* LLM Configuration Card */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6">
        <div className="flex items-center gap-3 mb-4">
          <Cpu className="text-purple-400" size={20} />
          <h3 className="text-lg font-semibold text-white">LLM Configuration</h3>
        </div>
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-slate-400 mb-2">Endpoint URL (OpenAI Compatible)</label>
              <input
                type="text"
                value={settings.llm_config.llm_endpoint || ''}
                onChange={(e) => setSettings({ ...settings, llm_config: { ...settings.llm_config, llm_endpoint: e.target.value } })}
                className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="https://api.openai.com/v1"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-2">API Key (Optional)</label>
              <input
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
                <label className="block text-sm text-slate-400">Model</label>
                <button
                  onClick={() => setManualModelEntry(!manualModelEntry)}
                  className="text-xs text-indigo-400 hover:text-indigo-300 underline"
                >
                  {manualModelEntry ? "Select from list" : "Enter manually"}
                </button>
              </div>
              {manualModelEntry ? (
                <input
                  type="text"
                  value={settings.llm_config.llm_model}
                  onChange={(e) => setSettings({ ...settings, llm_config: { ...settings.llm_config, llm_model: e.target.value } })}
                  className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  placeholder="e.g. gpt-4o"
                />
              ) : (
                <select
                  value={settings.llm_config.llm_model}
                  onChange={(e) => setSettings({ ...settings, llm_config: { ...settings.llm_config, llm_model: e.target.value } })}
                  className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
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
            <label className="block text-sm text-slate-400 mb-2">
              Temperature: {settings.llm_config.temperature.toFixed(1)}
            </label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={settings.llm_config.temperature}
              onChange={(e) => setSettings({ ...settings, llm_config: { ...settings.llm_config, temperature: parseFloat(e.target.value) } })}
              className="w-full"
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
              <label className="block text-sm text-slate-400 mb-2">Embedding Provider</label>
              <select
                value={settings.embedding_config?.provider || 'openai'}
                onChange={(e) => setSettings({ ...settings, embedding_config: { ...settings.embedding_config, provider: e.target.value } })}
                className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="openai">OpenAI</option>
                <option value="azure">Azure OpenAI</option>
                <option value="openai_compatible">OpenAI Compatible (Custom)</option>
                <option value="huggingface">HuggingFace (Local)</option>
              </select>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-slate-400 mb-2">Embedding Model</label>
                <input
                  type="text"
                  value={settings.embedding_config?.model || ''}
                  onChange={(e) => setSettings({ ...settings, embedding_config: { ...settings.embedding_config, model: e.target.value } })}
                  className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  placeholder="e.g. text-embedding-3-small"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-2">Dimensions</label>
                <input
                  type="number"
                  value={settings.embedding_config?.dimensions || 1536}
                  onChange={(e) => setSettings({ ...settings, embedding_config: { ...settings.embedding_config, dimensions: parseInt(e.target.value) } })}
                  className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            </div>

            {(settings.embedding_config?.provider === 'openai_compatible' || settings.embedding_config?.provider === 'azure') && (
              <div>
                <label className="block text-sm text-slate-400 mb-2">Base URL / Endpoint</label>
                <input
                  type="text"
                  value={settings.embedding_config?.base_url || ''}
                  onChange={(e) => setSettings({ ...settings, embedding_config: { ...settings.embedding_config, base_url: e.target.value } })}
                  className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  placeholder="https://..."
                />
              </div>
            )}

            <div>
              <label className="block text-sm text-slate-400 mb-2">API Key</label>
              <input
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
              <label className="block text-sm text-slate-400 mb-2">Values Provider</label>
              <input
                type="text"
                value={settings.vector_config.provider}
                onChange={(e) => setSettings({ ...settings, vector_config: { ...settings.vector_config, provider: e.target.value } })}
                className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-slate-400 mb-2">Host</label>
                <input
                  type="text"
                  value={settings.vector_config.host}
                  onChange={(e) => setSettings({ ...settings, vector_config: { ...settings.vector_config, host: e.target.value } })}
                  className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-2">Port</label>
                <input
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

      {/* API Client Configuration Card */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6">
        <div className="flex items-center gap-3 mb-4">
          <Key className="text-amber-400" size={20} />
          <h3 className="text-lg font-semibold text-white">API Client Configuration</h3>
        </div>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-slate-400 mb-2">Backend URL</label>
            <input
              type="text"
              value={apiBaseUrl}
              onChange={(e) => setApiBaseUrl(e.target.value)}
              className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="http://localhost:8000/api/v1"
            />
            <p className="text-xs text-slate-500 mt-1">The base URL of your backend API server</p>
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-2">API Key</label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="dev-api-key-12345"
            />
            <p className="text-xs text-slate-500 mt-1">Authentication key for backend API access</p>
          </div>

          <button
            onClick={handleSaveApiConfig}
            className="flex items-center gap-2 px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-lg"
          >
            <Save size={16} />
            Save API Configuration
          </button>

          <div className="p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg">
            <p className="text-sm text-blue-300">
              💡 <strong>Note:</strong> After saving, please refresh the page for the changes to take effect.
            </p>
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
            <label className="block text-sm text-slate-400 mb-2">Application Name</label>
            <input
              type="text"
              value={settings.app_meta.app_name}
              onChange={(e) => setSettings({ ...settings, app_meta: { ...settings.app_meta, app_name: e.target.value } })}
              className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-2">Version</label>
            <input
              type="text"
              value={settings.app_meta.version}
              onChange={(e) => setSettings({ ...settings, app_meta: { ...settings.app_meta, version: e.target.value } })}
              className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-2">Project Name</label>
            <input
              type="text"
              value={settings.app_meta.project_name}
              onChange={(e) => setSettings({ ...settings, app_meta: { ...settings.app_meta, project_name: e.target.value } })}
              className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>
      </div>

      <ConnectionDialog
        isOpen={showConnectionDialog}
        onClose={() => setShowConnectionDialog(false)}
        onSave={handleConnectionSave}
        initialValues={{
          driver: settings?.target_db?.driver || settings?.target_db?.connection_string_decrypted?.match(/DRIVER=\{([^}]*)\}/)?.[1] || 'ODBC Driver 17 for SQL Server',
          server: settings?.target_db?.server || '',
          database: settings?.target_db?.database_name || '',
          authType: (settings?.target_db?.auth_type as AuthType)
            || (settings?.target_db?.connection_string_decrypted?.match(/Authentication=([^;]*)/)?.[1]?.toLowerCase() as AuthType)
            || (settings?.target_db?.connection_string_decrypted?.match(/AUTHENTICATION=([^;]*)/)?.[1]?.toLowerCase() as AuthType)
            || 'sql',
          username: settings?.target_db?.username || '',
          trustServerCertificate: settings?.target_db?.trust_server_certificate ?? false
        }}
      />
    </div >
  );
};
