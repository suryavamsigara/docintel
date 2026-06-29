import React from 'react';
import { CheckCircle2, Loader2, Circle, AlertCircle } from 'lucide-react';

export default function PipelineTab({ stages }) {
  // We added cross_document right before the CRM sync!
  const steps = [
    { id: 'ingestion', label: 'Format Analysis & Layout Mapping' },
    { id: 'classification', label: 'Document Identification' },
    { id: 'extraction', label: 'Entity & Clause Extraction' },
    { id: 'anomaly', label: 'Anomaly & Risk Detection' },
    { id: 'cross_document', label: 'Cross-Document Contradiction Check' }, 
    { id: 'crm', label: 'CRM Synchronization' } 
  ];

  return (
    <div className="max-w-2xl mx-auto p-4 md:p-8">
      <div className="relative">
        {/* Vertical line connecting the steps */}
        <div className="absolute left-[19px] top-6 bottom-6 w-0.5 bg-gray-100" />
        
        <div className="space-y-8 relative">
          {steps.map((step) => {
            const stageData = stages?.[step.id] || { status: 'pending' };
            const isComplete = stageData.status === 'complete';
            const isRunning = stageData.status === 'running';
            const isError = stageData.status === 'error';
            
            return (
              <div key={step.id} className="flex items-start">
                <div className="relative z-10 flex items-center justify-center w-10 h-10 bg-white rounded-full">
                  {isComplete ? (
                    <CheckCircle2 className="w-6 h-6 text-emerald-500 bg-white" />
                  ) : isRunning ? (
                    <Loader2 className="w-6 h-6 text-blue-500 animate-spin bg-white" />
                  ) : isError ? (
                    <AlertCircle className="w-6 h-6 text-rose-500 bg-white" />
                  ) : (
                    <Circle className="w-6 h-6 text-gray-300 bg-white" />
                  )}
                </div>
                
                <div className="ml-4 mt-1">
                  <h4 className={`text-sm font-bold ${isRunning ? 'text-blue-700' : isComplete ? 'text-gray-900' : 'text-gray-400'}`}>
                    {step.label}
                  </h4>
                  <p className={`text-sm mt-1 ${isError ? 'text-rose-600' : 'text-gray-500'}`}>
                    {stageData.detail || (
                      isComplete ? 'Completed successfully.' :
                      isRunning ? 'Processing...' :
                      isError ? stageData.error :
                      'Waiting in queue...'
                    )}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}