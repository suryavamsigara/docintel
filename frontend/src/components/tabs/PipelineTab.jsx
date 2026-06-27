import React from 'react';
import { Loader2, CheckCircle2, CircleDashed, ChevronRight } from 'lucide-react';

export default function PipelineTab({ stages }) {
  const renderStage = (key, title, waitingText) => {
    const stage = stages[key];
    const status = stage?.status || 'pending';
    const detail = stage?.detail;

    let Icon = <CircleDashed className="w-5 h-5 text-gray-300" />;
    let statusClasses = "opacity-40";
    
    if (status === 'running') {
      Icon = <Loader2 className="w-5 h-5 text-blue-600 animate-spin" />;
      statusClasses = "bg-white border-blue-200 shadow-sm ring-1 ring-blue-500/10";
    } else if (status === 'complete') {
      Icon = <CheckCircle2 className="w-5 h-5 text-emerald-500" />;
      statusClasses = "bg-white border-gray-200 shadow-sm";
    }

    return (
      <div className={`mb-3 rounded-xl border p-4 transition-all duration-500 ${statusClasses}`}>
        <div className="flex items-center space-x-4">
          {Icon}
          <div className="flex-1">
            <h4 className="font-semibold text-gray-900 text-sm">{title}</h4>
            <p className={`text-xs mt-1 ${status === 'running' ? 'text-blue-600 animate-pulse' : 'text-gray-500'}`}>
              {status === 'pending' ? waitingText : detail || "Completed successfully."}
            </p>
          </div>
          {status === 'complete' && stage.data && (
             <button className="text-xs text-blue-600 hover:underline flex items-center font-medium">
               View <ChevronRight className="w-3 h-3 ml-1" />
             </button>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="max-w-xl mx-auto py-4">
      {renderStage('ingestion', 'Format Analysis & Layout Mapping', 'Waiting for document upload...')}
      {renderStage('classification', 'Document Identification', 'Waiting for text extraction...')}
      {renderStage('extraction', 'Entity & Clause Extraction', 'Waiting for classification...')}
      
      {/* Stubs for future implementation */}
      {renderStage('anomaly', 'Anomaly & Risk Detection', 'Waiting for clauses...')}
      {renderStage('crm', 'CRM Synchronization', 'Waiting for final validation...')}
    </div>
  );
}