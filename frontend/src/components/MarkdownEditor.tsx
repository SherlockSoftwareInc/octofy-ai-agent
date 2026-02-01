import React from 'react';

interface MarkdownEditorProps {
    content: string;
    onChange: (content: string) => void;
    className?: string;
    placeholder?: string;
}

export const MarkdownEditor: React.FC<MarkdownEditorProps> = ({
    content,
    onChange,
    className = '',
    placeholder = 'Enter markdown content...',
}) => {
    return (
        <textarea
            value={content}
            onChange={(e) => onChange(e.target.value)}
            className={`w-full px-4 py-3 bg-slate-950/80 border border-slate-700 rounded-lg text-slate-200 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none ${className}`}
            spellCheck={false}
            placeholder={placeholder}
        />
    );
};
