/**
 * RefinementSuggestions Component
 * 
 * Displays clickable suggestions for refining the current analysis.
 * Suggestions are generated based on data profile and insights.
 */

import React from 'react';
import { 
  ArrowRight,
  Filter,
  Layers,
  Calendar,
  TrendingUp,
  Sparkles
} from 'lucide-react';

interface RefinementSuggestionsProps {
  suggestions: string[];
  onSuggestionClick: (suggestion: string) => void;
  className?: string;
}

// Map suggestion keywords to appropriate icons
const getSuggestionIcon = (suggestion: string): React.ComponentType<any> => {
  const lower = suggestion.toLowerCase();
  
  if (lower.includes('drill') || lower.includes('breakdown') || lower.includes('group')) {
    return Layers;
  }
  if (lower.includes('filter') || lower.includes('focus') || lower.includes('exclude')) {
    return Filter;
  }
  if (lower.includes('compare') || lower.includes('previous') || lower.includes('last')) {
    return Calendar;
  }
  if (lower.includes('trend') || lower.includes('over time') || lower.includes('timeline')) {
    return TrendingUp;
  }
  
  return Sparkles;
};

export const RefinementSuggestions: React.FC<RefinementSuggestionsProps> = ({
  suggestions,
  onSuggestionClick,
  className = ''
}) => {
  if (!suggestions || suggestions.length === 0) {
    return null;
  }

  return (
    <div className={`space-y-2 ${className}`}>
      <div className="flex items-center gap-2 text-sm text-gray-600">
        <ArrowRight className="w-4 h-4" />
        <span className="font-medium">Suggested refinements:</span>
      </div>

      <div className="flex flex-wrap gap-2">
        {suggestions.map((suggestion, index) => {
          const Icon = getSuggestionIcon(suggestion);
          
          return (
            <button
              key={index}
              onClick={() => onSuggestionClick(suggestion)}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg 
                       bg-gradient-to-r from-purple-50 to-blue-50 
                       border border-purple-200 
                       text-sm text-gray-800 font-medium
                       hover:from-purple-100 hover:to-blue-100 
                       hover:border-purple-300 hover:shadow-sm
                       active:scale-95
                       transition-all duration-150 ease-out
                       focus:outline-none focus:ring-2 focus:ring-purple-400 focus:ring-offset-1"
              title={`Click to: ${suggestion}`}
            >
              <Icon className="w-4 h-4 text-purple-600 flex-shrink-0" />
              <span className="leading-none">{suggestion}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default RefinementSuggestions;
