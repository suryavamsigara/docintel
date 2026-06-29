import React, { useState, useEffect } from 'react';
import { useParams, useLocation } from 'react-router-dom';
import { AlertTriangle, Search, FileX, Loader2 } from 'lucide-react';
import PipelineTab from '../components/tabs/PipelineTab';
import ClassificationTab from '../components/tabs/ClassificationTab';
import ExtractionTab from '../components/tabs/ExtractionTab';
import OverviewTab from '../components/tabs/OverviewTab';
import AnomaliesTab from '../components/tabs/AnomaliesTab';

// Strict order of pipeline execution
const STAGE_ORDER = ['ingestion', 'classification', 'extraction', 'anomaly', 'risk', 'cross_document'];

export default function DocumentWorkspace() {
  const { docId } = useParams();
  const location = useLocation();
  
  const [loading, setLoading] = useState(true);
  const [document, setDocument] = useState({
    id: docId,
    name: 'Loading...',
    type: 'application/pdf',
    fileUrl: location.state?.fileUrl || null,
    status: 'processing',
    stages: {
      ingestion: { status: 'pending' },
      classification: { status: 'pending' },
      extraction: { status: 'pending' },
      anomaly: { status: 'pending' },
      risk: { status: 'pending' }
    }
  });

  const [activeTab, setActiveTab] = useState('PIPELINE');
  const [currentPage, setCurrentPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');

  // 1. Initial Fetch to get Document Name and check if it's already finished
  useEffect(() => {
    const fetchDocInfo = async () => {
      try {
        const res = await fetch(`http://localhost:8000/api/documents/${docId}`);
        if (res.ok) {
          const data = await res.json();
          setDocument(prev => ({
            ...prev,
            name: data.name,
            status: data.status,
            // If the DB already has the final completed stages, load them!
            stages: data.stages || prev.stages 
          }));
          if (data.status === 'completed') setActiveTab('OVERVIEW');
        }
      } catch (err) {
        console.error("Failed to fetch doc info", err);
      } finally {
        setLoading(false);
      }
    };
    fetchDocInfo();
  }, [docId]);

  // 2. Establish live WebSocket connection for real-time updates
  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/${docId}`);
    
    ws.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      
      setDocument(prev => {
        const newStages = { ...prev.stages };
        
        // Update the current stage
        newStages[payload.stage] = {
          status: payload.status,
          detail: payload.detail || newStages[payload.stage]?.detail,
          data: payload.data || newStages[payload.stage]?.data,
          error: payload.error || null,
        };

        // NEW LOGIC: "Catch-Up" for missed WebSocket messages
        const stageIdx = STAGE_ORDER.indexOf(payload.stage);
        if (stageIdx > 0) {
          for (let i = 0; i < stageIdx; i++) {
            const pastStage = STAGE_ORDER[i];
            if (newStages[pastStage]?.status === 'pending' || newStages[pastStage]?.status === 'running') {
              newStages[pastStage] = {
                ...newStages[pastStage],
                status: 'complete',
                detail: 'Completed successfully'
              };
            }
          }
        }

        const status = (payload.stage === 'risk' && payload.status === 'complete') ? 'completed' : prev.status;
        return { ...prev, stages: newStages, status };
      });
    };
    
    return () => ws.close();
  }, [docId]);

  // Auto-switch tabs when finished
  useEffect(() => {
    if (document.status === 'completed' && activeTab === 'PIPELINE') setActiveTab('OVERVIEW');
  }, [document.status]);

  const handleJumpToPage = (pageNum) => {
    if (pageNum) setCurrentPage(pageNum);
  };

  const isLowQuality = document.stages.ingestion?.data?.low_quality;
  const pdfUrl = document.type === 'application/pdf' && document.fileUrl
    ? `${document.fileUrl}#page=${currentPage}&toolbar=0&view=FitH` 
    : document.fileUrl;

  const tabs = [
    { id: 'OVERVIEW', label: 'Overview', show: document.status === 'completed' },
    { id: 'PIPELINE', label: 'Pipeline', show: true },
    { id: 'CLASSIFICATION', label: 'Classification', show: !!document.stages.classification?.data },
    { id: 'EXTRACTION', label: 'Data & Clauses', show: !!document.stages.extraction?.data },
    { id: 'ANOMALIES', label: 'Anomalies & Risk', show: !!document.stages.anomaly?.data },
  ].filter(t => t.show);

  if (loading) return <div className="flex h-screen items-center justify-center"><Loader2 className="w-8 h-8 text-blue-500 animate-spin" /></div>;

  return (
    <div className="flex w-full overflow-hidden h-[calc(100vh-3.5rem)]">
      
      {/* Left: Native Document Viewer */}
      <div className="w-1/2 h-full bg-[#323639] border-r border-gray-300 relative shadow-inner">
        {!document.fileUrl ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center p-8 text-center bg-[#323639]">
             <FileX className="w-12 h-12 text-gray-500 mb-3" />
             <p className="text-gray-400 font-medium text-lg">Document Viewer Unavailable</p>
             <p className="text-sm text-gray-500 mt-2 max-w-sm">Because the document was processed in a different session, the local file reference is gone. Connect AWS S3 to enable persistent rendering.</p>
          </div>
        ) : document.type === 'application/pdf' ? (
          <iframe src={pdfUrl} className="absolute inset-0 w-full h-full border-none" title="Viewer" />
        ) : (
          <div className="absolute inset-0 w-full h-full flex items-center justify-center p-4">
            <img src={pdfUrl} alt="Document" className="max-w-full max-h-full object-contain shadow-2xl" />
          </div>
        )}
      </div>

      {/* Right: Analysis Tabs */}
      <div className="w-1/2 h-full bg-[#F9FAFB] flex flex-col relative">
        {isLowQuality && (
          <div className="bg-amber-50 border-b border-amber-200 px-6 py-3 flex items-start shrink-0">
            <AlertTriangle className="w-5 h-5 text-amber-600 mr-3 shrink-0 mt-0.5" />
            <p className="text-sm font-medium text-amber-800 leading-snug">
              Low quality scan detected. OCR confidence is below threshold; some extracted text may contain errors.
            </p>
          </div>
        )}

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
          
          {activeTab !== 'PIPELINE' && (
            <div className="pb-2 relative ml-4 shrink-0">
              <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1.5" />
              <input 
                type="text" 
                placeholder="Filter..." 
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 pr-3 py-1 text-sm bg-gray-50 border border-gray-200 rounded-full focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 w-32 transition-all"
              />
            </div>
          )}
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {activeTab === 'OVERVIEW' && <OverviewTab doc={document} />}
          {activeTab === 'PIPELINE' && <PipelineTab stages={document.stages} />}
          {activeTab === 'CLASSIFICATION' && <ClassificationTab data={document.stages.classification?.data} onJump={handleJumpToPage} filter={searchQuery} />}
          {activeTab === 'EXTRACTION' && <ExtractionTab data={document.stages.extraction?.data} onJump={handleJumpToPage} filter={searchQuery} />}
          {activeTab === 'ANOMALIES' && <AnomaliesTab anomalyData={document.stages.anomaly?.data} riskData={document.stages.risk?.data} onJump={handleJumpToPage} />}
        </div>
      </div>
    </div>
  );
}