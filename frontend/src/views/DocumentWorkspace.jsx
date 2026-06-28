import React, { useState, useEffect } from 'react';
import { AlertTriangle, Search } from 'lucide-react';
import PipelineTab from '../components/tabs/PipelineTab';
import ClassificationTab from '../components/tabs/ClassificationTab';
import ExtractionTab from '../components/tabs/ExtractionTab';
import OverviewTab from '../components/tabs/OverviewTab';
import AnomaliesTab from '../components/tabs/AnomaliesTab';

export default function DocumentWorkspace({ document }) {
  const [activeTab, setActiveTab] = useState(document.status === 'completed' ? 'OVERVIEW' : 'PIPELINE');
  const [currentPage, setCurrentPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    if (document.status === 'completed' && activeTab === 'PIPELINE') setActiveTab('OVERVIEW');
  }, [document.status]);

  const handleJumpToPage = (pageNum) => {
    if (pageNum) setCurrentPage(pageNum);
  };

  const isLowQuality = document.stages.ingestion?.data?.low_quality;
  
  const pdfUrl = document.type === 'application/pdf' 
    ? `${document.fileUrl}#page=${currentPage}&toolbar=0&view=FitH` 
    : document.fileUrl;

  const tabs = [
    { id: 'OVERVIEW', label: 'Overview', show: document.status === 'completed' },
    { id: 'PIPELINE', label: 'Pipeline', show: true },
    { id: 'CLASSIFICATION', label: 'Classification', show: !!document.stages.classification?.data },
    { id: 'EXTRACTION', label: 'Data & Clauses', show: !!document.stages.extraction?.data },
    // NEW TAB HERE:
    { id: 'ANOMALIES', label: 'Anomalies & Risk', show: !!document.stages.anomaly?.data },
  ].filter(t => t.show);

  return (
    <div className="flex w-full overflow-hidden h-[calc(100vh-3.5rem)]">
      
      {/* Left: Native Document Viewer (Reverted to 50% width) */}
      <div className="w-1/2 h-full bg-[#323639] border-r border-gray-300 relative shadow-inner">
        {document.type === 'application/pdf' ? (
          <iframe 
            src={pdfUrl} 
            className="absolute inset-0 w-full h-full border-none" 
            title="Viewer" 
          />
        ) : (
          <div className="absolute inset-0 w-full h-full flex items-center justify-center p-4">
            <img src={pdfUrl} alt="Document" className="max-w-full max-h-full object-contain shadow-2xl" />
          </div>
        )}
      </div>

      {/* Right: Analysis Tabs (Reverted to 50% width) */}
      <div className="w-1/2 h-full bg-[#F9FAFB] flex flex-col relative">
        
        {/* OCR Warning Banner */}
        {isLowQuality && (
          <div className="bg-amber-50 border-b border-amber-200 px-6 py-3 flex items-start shrink-0">
            <AlertTriangle className="w-5 h-5 text-amber-600 mr-3 shrink-0 mt-0.5" />
            <p className="text-sm font-medium text-amber-800 leading-snug">
              Low quality scan detected. OCR confidence is below threshold; some extracted text may contain errors.
            </p>
          </div>
        )}

        {/* Tab Headers */}
        <div className="px-6 pt-4 pb-0 bg-white border-b border-gray-200 shrink-0 flex justify-between items-end">
          <div className="flex space-x-6 overflow-x-auto hide-scrollbar">
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`pb-3 text-sm font-medium transition-colors border-b-2 whitespace-nowrap ${
                  activeTab === tab.id ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-900'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
          
          {/* Search/Filter Box */}
          {activeTab !== 'PIPELINE' && (
            <div className="pb-2 relative ml-4 shrink-0">
              <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1.5" />
              <input 
                type="text" 
                placeholder="Filter..." 
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 pr-3 py-1 text-sm bg-gray-50 border border-gray-200 rounded-full focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 w-32 xl:w-48 transition-all"
              />
            </div>
          )}
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto p-6">
          {activeTab === 'OVERVIEW' && <OverviewTab doc={document} />}
          {activeTab === 'PIPELINE' && <PipelineTab stages={document.stages} />}
          {activeTab === 'CLASSIFICATION' && <ClassificationTab data={document.stages.classification?.data} onJump={handleJumpToPage} filter={searchQuery} />}
          {activeTab === 'EXTRACTION' && <ExtractionTab data={document.stages.extraction?.data} onJump={handleJumpToPage} filter={searchQuery} />}
          {activeTab === 'ANOMALIES' && (
             <AnomaliesTab 
               anomalyData={document.stages.anomaly?.data} 
               riskData={document.stages.risk?.data} 
               onJump={handleJumpToPage} 
             />
          )}
        </div>
      </div>
    </div>
  );
}