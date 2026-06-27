import React, { useState, useEffect } from 'react';
import PipelineTab from '../components/tabs/PipelineTab';
import ClassificationTab from '../components/tabs/ClassificationTab';
import ExtractionTab from '../components/tabs/ExtractionTab';
import OverviewTab from '../components/tabs/OverviewTab';

export default function DocumentWorkspace({ document }) {
  // If processing is done, default to Overview. Otherwise, default to Pipeline.
  const [activeTab, setActiveTab] = useState(document.status === 'completed' ? 'OVERVIEW' : 'PIPELINE');

  // Auto-switch to overview when processing finishes
  useEffect(() => {
    if (document.status === 'completed' && activeTab === 'PIPELINE') {
      setActiveTab('OVERVIEW');
    }
  }, [document.status]);

  const tabs = [
    { id: 'OVERVIEW', label: 'Overview', show: document.status === 'completed' },
    { id: 'PIPELINE', label: 'Pipeline', show: true },
    { id: 'CLASSIFICATION', label: 'Classification', show: !!document.stages.classification?.data },
    { id: 'EXTRACTION', label: 'Data & Clauses', show: !!document.stages.extraction?.data },
  ].filter(t => t.show);

  return (
    <div className="flex h-full w-full overflow-hidden">
      
      {/* Left: Native Document Viewer */}
      <div className="w-1/2 h-full bg-gray-900 border-r border-gray-300 flex flex-col">
        {document.type === 'application/pdf' ? (
          <iframe 
            src={`${document.fileUrl}#toolbar=0`} 
            className="w-full h-full bg-white" 
            title="Document Viewer"
          />
        ) : document.type.startsWith('image/') ? (
          <div className="w-full h-full overflow-auto flex items-center justify-center p-4">
            <img src={document.fileUrl} alt="Document" className="max-w-full shadow-2xl bg-white" />
          </div>
        ) : (
           <div className="m-auto text-center text-gray-400">Preview not available for this file type.</div>
        )}
      </div>

      {/* Right: Analysis Tabs */}
      <div className="w-1/2 h-full bg-[#F9FAFB] flex flex-col relative">
        
        {/* Segmented Control Header */}
        <div className="px-6 pt-4 pb-0 bg-white border-b border-gray-200 shrink-0">
          <div className="flex space-x-6">
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`pb-3 text-sm font-medium transition-colors border-b-2 ${
                  activeTab === tab.id 
                    ? 'border-blue-600 text-blue-600' 
                    : 'border-transparent text-gray-500 hover:text-gray-900'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Tab Content Area */}
        <div className="flex-1 overflow-y-auto p-6">
          {activeTab === 'OVERVIEW' && <OverviewTab doc={document} />}
          {activeTab === 'PIPELINE' && <PipelineTab stages={document.stages} />}
          {activeTab === 'CLASSIFICATION' && <ClassificationTab data={document.stages.classification?.data} />}
          {activeTab === 'EXTRACTION' && <ExtractionTab data={document.stages.extraction?.data} />}
        </div>
      </div>

    </div>
  );
}