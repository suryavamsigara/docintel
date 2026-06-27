import React, { useState } from 'react';
import { CheckCircle2, CircleDashed, AlertCircle, ChevronDown, ChevronRight, Loader2 } from 'lucide-react';

export default function PipelineStage({ title, state, description }) {
  const [isExpanded, setIsExpanded] = useState(true);
  const { status, data, error } = state;

  const getStatusIcon = () => {
    switch (status) {
      case 'running':
        return <Loader2 className="w-5 h-5 text-ios-blue animate-spin" />;
      case 'complete':
        return <CheckCircle2 className="w-5 h-5 text-ios-green" />;
      case 'error':
        return <AlertCircle className="w-5 h-5 text-ios-red" />;
      default:
        return <CircleDashed className="w-5 h-5 text-ios-grayDark opacity-50" />;
    }
  };

  return (
    <div className="mb-4 bg-white rounded-2xl shadow-apple border border-gray-100 overflow-hidden transition-all">
      <button 
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-4 bg-white hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center space-x-4">
          {getStatusIcon()}
          <div className="text-left">
            <h3 className="font-semibold text-gray-900 tracking-tight">{title}</h3>
            <p className="text-xs text-gray-500">{description}</p>
          </div>
        </div>
        {data && (
          isExpanded ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronRight className="w-4 h-4 text-gray-400" />
        )}
      </button>

      {/* Output Panel (Collapsible) */}
      {isExpanded && (data || error) && (
        <div className="px-4 pb-4 pt-2 bg-gray-50 border-t border-gray-100">
          {error ? (
            <div className="text-sm text-ios-red p-3 bg-red-50 rounded-xl">{error}</div>
          ) : (
            <pre className="text-xs text-gray-700 whitespace-pre-wrap font-mono p-3 bg-white rounded-xl shadow-apple-inset border border-gray-200">
              {JSON.stringify(data, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}