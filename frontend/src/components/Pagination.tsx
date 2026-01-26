import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

interface PaginationProps {
    currentPage: number; // 0-based index
    totalItems: number;
    pageSize?: number;
    onPageChange: (page: number) => void;
}

export const Pagination: React.FC<PaginationProps> = ({
    currentPage,
    totalItems,
    pageSize = 50,
    onPageChange,
}) => {
    const totalPages = Math.ceil(totalItems / pageSize);
    const startItem = currentPage * pageSize + 1;
    const endItem = Math.min((currentPage + 1) * pageSize, totalItems);

    // Keyboard navigation
    React.useEffect(() => {
        if (totalPages <= 1) {
            return;
        }
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'ArrowLeft' && currentPage > 0) {
                onPageChange(currentPage - 1);
            } else if (e.key === 'ArrowRight' && currentPage < totalPages - 1) {
                onPageChange(currentPage + 1);
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [currentPage, totalPages, onPageChange]);

    // Don't show pagination if there's only one page or no items
    if (totalPages <= 1) {
        return null;
    }

    const handlePrevious = () => {
        if (currentPage > 0) {
            onPageChange(currentPage - 1);
        }
    };

    const handleNext = () => {
        if (currentPage < totalPages - 1) {
            onPageChange(currentPage + 1);
        }
    };

    return (
        <div className="flex items-center justify-between px-6 py-4 bg-slate-900 border-t border-slate-800">
            <div className="text-sm text-slate-400">
                Showing <span className="font-medium text-slate-300">{startItem}</span> to{' '}
                <span className="font-medium text-slate-300">{endItem}</span> of{' '}
                <span className="font-medium text-slate-300">{totalItems}</span> results
            </div>

            <div className="flex items-center gap-2">
                <button
                    onClick={handlePrevious}
                    disabled={currentPage === 0}
                    className="flex items-center gap-1 px-3 py-2 bg-slate-800 rounded-lg hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition text-sm text-slate-300"
                    aria-label="Previous page"
                >
                    <ChevronLeft size={16} />
                    Previous
                </button>

                <div className="px-4 text-sm text-slate-300">
                    Page <span className="font-medium">{currentPage + 1}</span> of{' '}
                    <span className="font-medium">{totalPages}</span>
                </div>

                <button
                    onClick={handleNext}
                    disabled={currentPage >= totalPages - 1}
                    className="flex items-center gap-1 px-3 py-2 bg-slate-800 rounded-lg hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition text-sm text-slate-300"
                    aria-label="Next page"
                >
                    Next
                    <ChevronRight size={16} />
                </button>
            </div>
        </div>
    );
};
