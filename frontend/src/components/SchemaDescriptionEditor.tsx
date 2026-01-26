import React, { useState, useEffect } from 'react';
import { X, Save, Loader } from 'lucide-react';

interface SchemaDescriptionEditorProps {
    isOpen: boolean;
    onClose: () => void;
    onSave: (description: string) => Promise<void>;
    schemaName: string;
    tableName: string;
    currentDescription: string;
}

export const SchemaDescriptionEditor: React.FC<SchemaDescriptionEditorProps> = ({
    isOpen,
    onClose,
    onSave,
    schemaName,
    tableName,
    currentDescription
}) => {
    const [description, setDescription] = useState(currentDescription);
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        setDescription(currentDescription);
    }, [currentDescription, isOpen]);

    const handleSave = async () => {
        setSaving(true);
        try {
            await onSave(description);
            onClose();
        } catch (error) {
            alert(`Failed to save description: ${error}`);
        } finally {
            setSaving(false);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Escape') {
            onClose();
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onKeyDown={handleKeyDown}>
            <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 w-full max-w-2xl mx-4 max-h-[80vh] overflow-hidden flex flex-col">
                <div className="flex justify-between items-center mb-4">
                    <h3 className="text-lg font-semibold text-slate-200">
                        Edit Description: {schemaName}.{tableName}
                    </h3>
                    <button
                        onClick={onClose}
                        className="p-1 hover:bg-slate-800 rounded"
                        disabled={saving}
                    >
                        <X size={20} className="text-slate-400" />
                    </button>
                </div>

                <div className="flex-1 overflow-hidden">
                    <textarea
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        placeholder="Enter a description for this table..."
                        className="w-full h-full min-h-[200px] p-3 bg-slate-800 border border-slate-600 rounded-lg text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none"
                        disabled={saving}
                    />
                </div>

                <div className="flex justify-end gap-3 mt-4">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 bg-slate-700 text-slate-300 rounded-lg hover:bg-slate-600 transition disabled:opacity-50"
                        disabled={saving}
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleSave}
                        disabled={saving || description.trim() === currentDescription.trim()}
                        className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                    >
                        {saving ? (
                            <>
                                <Loader size={16} className="animate-spin" />
                                Saving...
                            </>
                        ) : (
                            <>
                                <Save size={16} />
                                Save Changes
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
};
