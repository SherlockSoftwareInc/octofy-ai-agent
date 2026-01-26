import { useState, type ReactNode, type FC } from 'react';
import { LayoutDashboard, Database, BookOpen, Layers, Settings, ArrowLeft, Gift } from 'lucide-react';

interface AdminLayoutProps {
    children: ReactNode;
    currentPage: string;
    onNavigate: (page: string) => void;
    isUploading?: boolean;
}

export const AdminLayout: FC<AdminLayoutProps> = ({ children, currentPage, onNavigate, isUploading = false }) => {
    const [confirmationDialog, setConfirmationDialog] = useState<{ visible: boolean; targetPage?: string }>({ visible: false });

    const handleNavigation = (page: string) => {
        if (isUploading) {
            setConfirmationDialog({ visible: true, targetPage: page });
        } else {
            performNavigation(page);
        }
    };

    const performNavigation = (page: string) => {
        if (page === 'back') {
            window.location.href = '/';
        } else {
            onNavigate(page);
        }
    };

    const confirmNavigation = () => {
        if (confirmationDialog.targetPage) {
            performNavigation(confirmationDialog.targetPage);
            setConfirmationDialog({ visible: false });
        }
    };

    return (
        <div className="flex min-h-screen h-screen w-screen overflow-hidden bg-slate-950 text-slate-200 font-sans">
            {/* Sidebar */}
            <aside className="w-64 flex-shrink-0 border-r border-slate-800 bg-slate-900/50 flex flex-col">
                <div className="p-6 border-b border-slate-800 flex items-center gap-2">
                    <LayoutDashboard className="text-indigo-500" />
                    <span className="font-bold text-lg tracking-tight">Agent Admin</span>
                </div>

                <nav className="flex-1 p-4 space-y-1">
                    <button
                        onClick={() => handleNavigation('schema')}
                        disabled={isUploading}
                        className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${currentPage === 'schema' ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30' : 'text-slate-400 hover:bg-slate-800 hover:text-white'} ${isUploading ? 'opacity-50 cursor-not-allowed' : ''}`}
                    >
                        <Database size={20} />
                        Schema Index
                    </button>

                    <button
                        onClick={() => handleNavigation('fewshot')}
                        disabled={isUploading}
                        className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${currentPage === 'fewshot' ? 'bg-emerald-600/20 text-emerald-300 border border-emerald-500/30' : 'text-slate-400 hover:bg-slate-800 hover:text-white'} ${isUploading ? 'opacity-50 cursor-not-allowed' : ''}`}
                    >
                        <BookOpen size={20} />
                        Knowledge Base
                    </button>

                    <button
                        onClick={() => handleNavigation('contributions')}
                        disabled={isUploading}
                        className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${currentPage === 'contributions' ? 'bg-amber-600/20 text-amber-300 border border-amber-500/30' : 'text-slate-400 hover:bg-slate-800 hover:text-white'} ${isUploading ? 'opacity-50 cursor-not-allowed' : ''}`}
                    >
                        <Gift size={20} />
                        Contributions
                    </button>

                    <button
                        onClick={() => handleNavigation('values')}
                        disabled={isUploading}
                        className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${currentPage === 'values' ? 'bg-purple-600/20 text-purple-300 border border-purple-500/30' : 'text-slate-400 hover:bg-slate-800 hover:text-white'} ${isUploading ? 'opacity-50 cursor-not-allowed' : ''}`}
                    >
                        <Layers size={20} />
                        Value Index
                    </button>

                    {/* Separator */}
                    <div className="border-t border-slate-800 my-2"></div>

                    <button
                        onClick={() => handleNavigation('settings')}
                        disabled={isUploading}
                        className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${currentPage === 'settings' ? 'bg-slate-600/20 text-slate-300 border border-slate-500/30' : 'text-slate-400 hover:bg-slate-800 hover:text-white'} ${isUploading ? 'opacity-50 cursor-not-allowed' : ''}`}
                    >
                        <Settings size={20} />
                        Settings
                    </button>

                    {/* Separator */}
                    <div className="border-t border-slate-800 my-2"></div>

                    <button
                        onClick={() => handleNavigation('back')}
                        disabled={isUploading}
                        className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-slate-400 hover:bg-slate-800 hover:text-white transition-all ${isUploading ? 'opacity-50 cursor-not-allowed' : ''}`}
                    >
                        <ArrowLeft size={20} />
                        Back to Chat
                    </button>
                </nav>

                <div className="p-4 border-t border-slate-800">
                    <div className="text-xs text-slate-500 text-center">
                        SQL Agent v1.0
                    </div>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 overflow-auto bg-slate-950 w-full">
                <div className="w-full h-full">
                    {children}
                </div>
            </main>

            {/* Confirmation Dialog */}
            {confirmationDialog.visible && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 backdrop-blur-sm">
                    <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 max-w-md shadow-2xl">
                        <h2 className="text-lg font-bold text-white mb-2">Upload in Progress</h2>
                        <p className="text-slate-300 mb-6">
                            A file upload is currently in progress. Are you sure you want to leave this page? The upload will be cancelled.
                        </p>
                        <div className="flex gap-3 justify-end">
                            <button
                                onClick={() => setConfirmationDialog({ visible: false })}
                                className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={confirmNavigation}
                                className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors"
                            >
                                Leave Page
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};
