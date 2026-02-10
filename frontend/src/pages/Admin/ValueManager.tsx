import { useState, useEffect, useMemo, type FC } from 'react';
import { Upload, Download, Trash2, Loader2, CheckCircle, AlertCircle, RefreshCw, Search } from 'lucide-react';
import { api } from '../../api/client';
import { Pagination } from '../../components/Pagination';
import { DataSourceSelector } from '../../components/DataSourceSelector';

interface ValueItem {
  id: number;
  value: string;
  schema_name: string;
  table_name: string;
  column_name: string;
}

interface UploadStatus {
  status: 'idle' | 'loading' | 'success' | 'error';
  message?: string;
  rowsProcessed?: number;
  totalRows?: number;
}

interface ValueManagerProps {
  onUploadStateChange?: (isUploading: boolean) => void;
}

export const ValueManager: FC<ValueManagerProps> = ({ onUploadStateChange }) => {
  const [values, setValues] = useState<ValueItem[]>([]);
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>({ status: 'idle' });
  const [isLoading, setIsLoading] = useState(false);
  const [uploadMode, setUploadMode] = useState<'append' | 'replace'>('append');
  const [uploadProgress, setUploadProgress] = useState(0);
  const [selectedSourceId, setSelectedSourceId] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(0);
  const [isSearching, setIsSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<ValueItem[] | null>(null);

  // Load all values on component mount
  useEffect(() => {
    loadValues();
  }, []);

  // Prevent page navigation during upload
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (uploadStatus.status === 'loading') {
        e.preventDefault();
        e.returnValue = 'Upload in progress. Are you sure you want to leave?';
        return 'Upload in progress. Are you sure you want to leave?';
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [uploadStatus.status]);

  // Notify parent when upload state changes
  useEffect(() => {
    if (onUploadStateChange) {
      onUploadStateChange(uploadStatus.status === 'loading');
    }
  }, [uploadStatus.status, onUploadStateChange]);

  const loadValues = async () => {
    setIsLoading(true);
    try {
      const values = await api.admin.getValues();
      setValues(values.map(v => ({
        id: v.id || 0,
        value: v.value,
        schema_name: v.schema_name,
        table_name: v.table_name,
        column_name: v.column_name
      })));
    } catch (error) {
      console.error('Error loading values:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validate data source selection
    if (!selectedSourceId) {
      setUploadStatus({
        status: 'error',
        message: 'Please select a data source before uploading.',
      });
      event.target.value = '';
      return;
    }

    // Validate file type
    const validTypes = ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'text/csv', 'application/vnd.ms-excel'];
    if (!validTypes.includes(file.type) && !file.name.endsWith('.xlsx') && !file.name.endsWith('.csv')) {
      setUploadStatus({
        status: 'error',
        message: 'Please upload an Excel (.xlsx) or CSV file',
      });
      return;
    }

    setUploadStatus({ status: 'loading' });
    setUploadProgress(0);

    try {
      const response = await api.admin.ingestValues(file, uploadMode, (progress) => {
        setUploadProgress(progress.percentage);
      }, selectedSourceId || undefined);

      setUploadStatus({
        status: 'success',
        message: response.message,
        rowsProcessed: response.rows_processed,
        totalRows: response.total_rows,
      });

      // Reload values after successful upload
      setTimeout(() => loadValues(), 1000);
    } catch (error) {
      const errorWithResponse = error as { response?: { data?: { detail?: string } } };
      setUploadStatus({
        status: 'error',
        message: errorWithResponse.response?.data?.detail || 'Error uploading file',
      });
    }

    // Reset file input
    event.target.value = '';
  };

  const downloadTemplate = async () => {
    try {
      const blob = await api.admin.getValueTemplate();

      // Create download link
      const url = window.URL.createObjectURL(new Blob([blob]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'value_index_template.xlsx');
      document.body.appendChild(link);
      link.click();
      link.parentNode?.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Error downloading template:', error);
    }
  };

  const downloadValues = async () => {
    try {
      const blob = await api.admin.exportValues();
      const url = window.URL.createObjectURL(new Blob([blob]));
      const link = document.createElement('a');
      link.href = url;
      const timestamp = new Date().toISOString().slice(0, 10);
      link.setAttribute('download', `value_index_${timestamp}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.parentNode?.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Error downloading values:', error);
      alert('Failed to download values');
    }
  };

  const deleteValue = async (id: number) => {
    if (!confirm('Are you sure you want to delete this value?')) return;

    try {
      await api.admin.deleteValue(id);
      setValues(values.filter(v => v.id !== id));
    } catch (error) {
      console.error('Error deleting value:', error);
    }
  };

  const clearAllValues = async () => {
    if (!selectedSourceId) {
      alert('Please select a data source first.');
      return;
    }
    if (!confirm('This will delete all values for the selected data source. Continue?')) return;

    try {
      await api.admin.clearAllValues(selectedSourceId);
      // Reload to show remaining values from other sources
      await loadValues();
      setUploadStatus({
        status: 'success',
        message: 'Values for the selected data source cleared from index',
      });
    } catch (error) {
      console.error('Error clearing values:', error);
      setUploadStatus({
        status: 'error',
        message: 'Error clearing values',
      });
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      // If search is empty, clear search results and show all values
      setSearchResults(null);
      setCurrentPage(0);
      return;
    }

    setIsSearching(true);
    setCurrentPage(0); // Reset page immediately

    try {
      const results = await api.admin.searchValues(searchQuery, 100); // Get top 100 results
      setSearchResults(results.map(v => ({
        id: v.id || 0,
        value: v.value,
        schema_name: v.schema_name,
        table_name: v.table_name,
        column_name: v.column_name
      })));
    } catch (error) {
      console.error('Error searching values:', error);
      alert('Failed to search values. Please try again.');
      // Reset to show all values on error
      setSearchResults(null);
    } finally {
      setIsSearching(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  const handleClearSearch = () => {
    setSearchQuery('');
    setSearchResults(null);
    setCurrentPage(0);
  };

  // Use search results if available, otherwise use all values
  const displayValues = searchResults !== null ? searchResults : values;

  // Filter and paginate values
  const filteredAndPaginatedValues = useMemo(() => {
    const PAGE_SIZE = 50;

    // Paginate (no filtering - already filtered by backend search)
    const startIndex = currentPage * PAGE_SIZE;
    const endIndex = startIndex + PAGE_SIZE;
    const paginated = displayValues.slice(startIndex, endIndex);

    return { items: paginated, totalItems: displayValues.length };
  }, [displayValues, currentPage]);

  // Reset to page 0 when search results change
  useEffect(() => {
    setCurrentPage(0);
  }, [searchResults]);

  return (
    <div className="p-6 w-full space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h2 className="text-2xl font-bold text-white mb-2">Value Index Manager</h2>
          <p className="text-slate-400">Upload and manage lookup values for database mapping</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={downloadValues}
            className="flex items-center gap-2 px-4 py-2 bg-slate-800 rounded-lg hover:bg-slate-700 transition"
            title="Download as Excel"
          >
            <Download size={18} />
            Download
          </button>
          <button
            onClick={loadValues}
            className="flex items-center gap-2 px-4 py-2 bg-slate-800 rounded-lg hover:bg-slate-700 transition"
          >
            <RefreshCw size={18} className={isLoading ? "animate-spin" : ""} />
            Refresh
          </button>
        </div>
      </div>

      {/* Upload Section */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Upload Values</h3>

        <div className="space-y-4">
          {/* Data Source Selection */}
          <DataSourceSelector
            selectedSourceId={selectedSourceId}
            onSourceChange={setSelectedSourceId}
            disabled={uploadStatus.status === 'loading'}
          />

          {/* Mode Selection */}
          <div className="flex gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                checked={uploadMode === 'append'}
                onChange={() => setUploadMode('append')}
                className="w-4 h-4"
              />
              <span className="text-slate-300">Append to existing values</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                checked={uploadMode === 'replace'}
                onChange={() => setUploadMode('replace')}
                className="w-4 h-4"
              />
              <span className="text-slate-300">Replace all values (clear first)</span>
            </label>
          </div>

          {/* Upload Area */}
          <div className={`border-2 border-dashed rounded-lg p-8 text-center transition ${!selectedSourceId ? 'border-slate-800 opacity-50 cursor-not-allowed' : 'border-slate-700 hover:border-indigo-500/50'}`}>
            <input
              type="file"
              id="file-upload"
              accept=".xlsx,.xls,.csv"
              onChange={handleFileUpload}
              disabled={uploadStatus.status === 'loading' || !selectedSourceId}
              className="hidden"
            />
            <label htmlFor="file-upload" className={`block ${!selectedSourceId ? 'cursor-not-allowed' : 'cursor-pointer'}`}>
              <Upload className="w-8 h-8 text-slate-400 mx-auto mb-2" />
              {!selectedSourceId ? (
                <p className="text-slate-500 font-medium">Select a data source above to enable upload</p>
              ) : (
                <>
                  <p className="text-slate-300 font-medium">Click to upload or drag and drop</p>
                  <p className="text-slate-500 text-sm">Excel (.xlsx) or CSV files</p>
                </>
              )}
            </label>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3 pt-2 justify-center">
            <button
              onClick={downloadTemplate}
              className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-lg transition"
            >
              <Download className="w-4 h-4" />
              Download Template
            </button>
            <button
              onClick={clearAllValues}
              disabled={values.length === 0 || !selectedSourceId}
              className="flex items-center gap-2 px-4 py-2 bg-red-900/20 hover:bg-red-900/30 text-red-400 hover:text-red-300 rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Trash2 className="w-4 h-4" />
              Clear Source Values
            </button>
          </div>

          {/* Progress Bar */}
          {uploadStatus.status === 'loading' && (
            <div className="space-y-3 bg-purple-500/10 border border-purple-500/30 rounded-lg p-4">
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2">
                  <Loader2 className="w-5 h-5 animate-spin text-purple-400" />
                  <div>
                    <p className="text-slate-300 font-medium">Uploading in progress...</p>
                    <p className="text-purple-300 text-sm">Processing values data</p>
                  </div>
                </div>
              </div>
              <progress
                className="progress-bar progress-bar--purple"
                value={uploadProgress}
                max={100}
                aria-label="Upload progress"
              />
              <p className="text-xs text-purple-300/70">Do not close this page or navigate away until the upload is complete</p>
            </div>
          )}

          {/* Status Messages */}
          {uploadStatus.status === 'success' && (
            <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-4 flex items-start gap-3">
              <CheckCircle className="w-5 h-5 text-emerald-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-emerald-300 font-medium">{uploadStatus.message}</p>
                {uploadStatus.rowsProcessed && (
                  <p className="text-emerald-300/70 text-sm">
                    Processed: {uploadStatus.rowsProcessed} of {uploadStatus.totalRows} rows
                  </p>
                )}
              </div>
            </div>
          )}

          {uploadStatus.status === 'error' && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-red-300 font-medium">Upload Failed</p>
                <p className="text-red-300/70 text-sm">{uploadStatus.message}</p>
              </div>
            </div>
          )}


        </div>
      </div>

      {/* Values List */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white">Indexed Values ({values.length})</h3>
          {isLoading && <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />}
        </div>

        {/* Search */}
        {values.length > 0 && (
          <div className="mb-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-500" size={18} />
              <input
                type="text"
                placeholder="Search by value... (Press Enter to search)"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isSearching}
                className="w-full pl-10 pr-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 transition disabled:opacity-50"
              />
              {searchQuery && (
                <button
                  onClick={handleClearSearch}
                  disabled={isSearching}
                  className="absolute right-3 top-1/2 transform -translate-y-1/2 text-slate-500 hover:text-slate-300 disabled:opacity-50"
                  aria-label="Clear search"
                >
                  ×
                </button>
              )}
            </div>
            {isSearching && (
              <div className="mt-2 text-sm text-purple-400 flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                Searching value index...
              </div>
            )}
            {searchResults !== null && (
              <div className="mt-2 text-sm text-slate-400">
                Found {searchResults.length} matching values
              </div>
            )}
          </div>
        )}

        {/* Values Table */}
        {filteredAndPaginatedValues.totalItems > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700">
                  <th className="text-left py-3 px-4 text-slate-400">Value</th>
                  <th className="text-left py-3 px-4 text-slate-400">Schema</th>
                  <th className="text-left py-3 px-4 text-slate-400">Table</th>
                  <th className="text-left py-3 px-4 text-slate-400">Column</th>
                  <th className="text-left py-3 px-4 text-slate-400">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredAndPaginatedValues.items.map((v, index) => (
                  <tr key={`${v.value}-${v.table_name}-${v.column_name}-${index}`} className="border-b border-slate-800 hover:bg-slate-800/50 transition">
                    <td className="py-3 px-4 text-slate-200 font-mono">{v.value}</td>
                    <td className="py-3 px-4 text-slate-400">{v.schema_name}</td>
                    <td className="py-3 px-4 text-slate-400">{v.table_name}</td>
                    <td className="py-3 px-4 text-slate-400">{v.column_name}</td>
                    <td className="py-3 px-4">
                      <button
                        onClick={() => deleteValue(v.id)}
                        className="text-red-400 hover:text-red-300 transition"
                        aria-label="Delete value"
                        title="Delete value"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-12">
            <p className="text-slate-400">
              {values.length === 0 ? 'No values indexed yet. Upload an Excel file to get started.' : `No results found for "${searchQuery}"`}
            </p>
            {searchQuery && values.length > 0 && (
              <button
                onClick={() => setSearchQuery('')}
                className="mt-2 text-purple-400 hover:text-purple-300 text-sm"
              >
                Clear search
              </button>
            )}
          </div>
        )}

        <Pagination
          currentPage={currentPage}
          totalItems={filteredAndPaginatedValues.totalItems}
          pageSize={50}
          onPageChange={setCurrentPage}
        />
      </div>

      {/* Info Section */}
      <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4">
        <h4 className="text-blue-300 font-semibold mb-2">📋 Excel Format Guide</h4>
        <ul className="text-blue-300/80 text-sm space-y-1">
          <li>• Column 1 (value): The exact database value</li>
          <li>• Column 2 (schema_name): Database schema (e.g., 'dbo')</li>
          <li>• Column 3 (table_name): Table name (e.g., 'Customers')</li>
          <li>• Column 4 (column_name): Column name (e.g., 'Country')</li>
          <li>• Column 5 (metadata): Optional JSON metadata</li>
        </ul>
      </div>
    </div>
  );
};
