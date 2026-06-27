import React from 'react';
import { CheckCircle2, CircleDashed, AlertCircle, Loader2 } from 'lucide-react';
import { ClassificationView, ExtractionView } from './RichResults';

export default function PipelineStage({ title, state, stageKey }) {
  const { status, data, error, detail } = state;

  const getStatusIcon = () => {
    switch (status) {
      case 'running': return <Loader2 className="w-5 h-5 text-ios-blue animate-spin" />;
      case 'complete': return <CheckCircle2 className="w-5 h-5 text-ios-green" />;
      case 'error': return <AlertCircle className="w-5 h-5 text-ios-red" />;
      default: return <CircleDashed className="w-5 h-5 text-gray-300" />;
    }
  };

  const isActive = status === 'running' || status === 'complete' || status === 'error';

  return (
    <div className={`mb-4 transition-all duration-300 ${isActive ? 'opacity-100' : 'opacity-40 pointer-events-none'}`}>
      <div className={`rounded-2xl border ${status === 'running' ? 'border-ios-blue bg-blue-50/10 shadow-sm' : 'border-gray-200 bg-white'}`}>
        
        {/* Header */}
        <div className="p-4 flex items-center space-x-4">
          {getStatusIcon()}
          <div className="flex-1">
            <h3 className="font-semibold text-gray-900 tracking-tight">{title}</h3>
            {status === 'running' && detail && (
              <p className="text-xs text-ios-blue mt-0.5 animate-pulse">{detail}</p>
            )}
            {status === 'complete' && detail && (
              <p className="text-xs text-gray-500 mt-0.5">{detail}</p>
            )}
          </div>
        </div>

        {/* Dynamic Output Panel */}
        {status === 'complete' && data && (
          <div className="px-4 pb-4">
            <div className="w-full h-[1px] bg-gray-100 mb-2"></div>
            
            {/* Inject the correct view based on the stage */}
            {stageKey === 'classification' && <ClassificationView data={data} />}
            {stageKey === 'extraction' && <ExtractionView data={data} />}
            
            {stageKey === 'ingestion' && (
               <div className="pt-2 flex gap-4 text-xs font-medium text-gray-500">
                 <span className="bg-gray-100 px-2 py-1 rounded-md">Pages: {data.pages_count}</span>
                 {data.ocr_used && <span className="bg-amber-50 text-amber-700 px-2 py-1 rounded-md border border-amber-200">OCR Engaged</span>}
               </div>
            )}
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="px-4 pb-4">
            <div className="text-sm text-rose-700 p-3 bg-rose-50 rounded-xl border border-rose-100">{error}</div>
          </div>
        )}
      </div>
    </div>
  );
}