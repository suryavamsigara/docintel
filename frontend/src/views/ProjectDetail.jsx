import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { FileText, UploadCloud, Loader2, CheckCircle2, ChevronRight, Cpu, Sparkles, GitPullRequest, AlertTriangle } from 'lucide-react';

export default function ProjectDetail() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  
  const [project, setProject] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [contradictions, setContradictions] = useState([]);
  const [activeTab, setActiveTab] = useState('DOCUMENTS'); // 'DOCUMENTS' | 'CONTRADICTIONS'
  
  const [loading, setLoading] = useState(true);
  const [isDragging, setIsDragging] = useState(false);
  const [processingMode, setProcessingMode] = useState('local');

  const fetchProjectData = useCallback(async () => {
    try {
      const [docsRes, contraRes] = await Promise.all([
        fetch(`http://localhost:8000/api/projects/${projectId}/documents`),
        fetch(`http://localhost:8000/api/projects/${projectId}/contradictions`)
      ]);
      if (docsRes.ok) setDocuments(await docsRes.json());
      if (contraRes.ok) setContradictions(await contraRes.json());
    } catch (err) {
      console.error("Failed to fetch project data", err);
    }
  }, [projectId]);

  useEffect(() => {
    const loadProject = async () => {
      try {
        const projRes = await fetch(`http://localhost:8000/api/projects/${projectId}`);
        if (projRes.ok) setProject(await projRes.json());
        await fetchProjectData();
      } catch (err) {
        console.error("Failed to load project", err);
      } finally {
        setLoading(false);
      }
    };
    loadProject();
  }, [projectId, fetchProjectData]);

  // Polling mechanism while processing
  useEffect(() => {
    let interval;
    if (documents.some(doc => doc.status === 'processing')) {
      interval = setInterval(fetchProjectData, 3000);
    }
    return () => clearInterval(interval);
  }, [documents, fetchProjectData]);

  const handleUpload = async (file, mode) => {
    if (!file) return;
    const tempId = Math.random().toString(36).substring(7);
    setDocuments(prev => [{ id: tempId, name: file.name, status: 'processing' }, ...prev]);
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('project_id', projectId);

    try {
      await fetch('http://localhost:8000/api/upload', {
        method: 'POST',
        headers: { 'X-Processing-Mode': mode },
        body: formData,
      });
      fetchProjectData();
      setActiveTab('DOCUMENTS');
    } catch (err) {
      console.error('Upload failed:', err);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files?.length) handleUpload(e.dataTransfer.files[0], processingMode);
  };

  if (loading) return <div className="p-12 text-center text-gray-500"><Loader2 className="w-6 h-6 animate-spin mx-auto mb-2" /> Loading project...</div>;
  if (!project) return <div className="p-12 text-center text-rose-500 font-bold">Project not found.</div>;

  return (
    <div className="max-w-5xl mx-auto p-8">
      <h1 className="text-3xl font-bold tracking-tight mb-8">{project.name}</h1>

      {/* Tabs */}
      <div className="flex border-b border-gray-200 mb-8 space-x-8">
        <button 
          onClick={() => setActiveTab('DOCUMENTS')}
          className={`pb-4 text-sm font-bold border-b-2 transition-colors ${activeTab === 'DOCUMENTS' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-900'}`}
        >
          Documents <span className="ml-2 bg-gray-100 text-gray-600 py-0.5 px-2 rounded-full text-xs">{documents.length}</span>
        </button>
        <button 
          onClick={() => setActiveTab('CONTRADICTIONS')}
          className={`pb-4 text-sm font-bold border-b-2 transition-colors flex items-center ${activeTab === 'CONTRADICTIONS' ? 'border-rose-600 text-rose-600' : 'border-transparent text-gray-500 hover:text-gray-900'}`}
        >
          <GitPullRequest className="w-4 h-4 mr-2" /> Contradictions 
          {contradictions.length > 0 && <span className="ml-2 bg-rose-100 text-rose-600 py-0.5 px-2 rounded-full text-xs">{contradictions.length}</span>}
        </button>
      </div>

      {activeTab === 'DOCUMENTS' ? (
        <>
          {/* Document List */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden mb-12">
            {documents.length === 0 ? (
              <div className="p-12 text-center text-gray-500">No documents in this project yet.</div>
            ) : (
              <div className="divide-y divide-gray-100">
                {documents.map(doc => (
                  <button key={doc.id} onClick={() => navigate(`/document/${doc.id}`)} className="w-full text-left p-4 hover:bg-gray-50 flex items-center justify-between transition-colors group">
                    <div className="flex items-center space-x-4">
                      <FileText className="w-8 h-8 text-blue-500 p-1.5 bg-blue-50 rounded-lg" />
                      <h4 className="font-medium text-gray-900">{doc.name}</h4>
                    </div>
                    <div className="flex items-center space-x-4">
                      {doc.status === 'processing' ? (
                        <span className="flex items-center text-xs font-medium text-amber-600 bg-amber-50 px-3 py-1 rounded-full border border-amber-200"><Loader2 className="w-3 h-3 mr-1.5 animate-spin" /> Processing</span>
                      ) : doc.status === 'failed' ? (
                         <span className="flex items-center text-xs font-medium text-rose-700 bg-rose-50 px-3 py-1 rounded-full border border-rose-200">Failed</span>
                      ) : (
                        <span className="flex items-center text-xs font-medium text-emerald-700 bg-emerald-50 px-3 py-1 rounded-full border border-emerald-200"><CheckCircle2 className="w-3 h-3 mr-1.5" /> Analyzed</span>
                      )}
                      <ChevronRight className="w-5 h-5 text-gray-300 group-hover:text-blue-500 transition-colors" />
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Upload Section */}
          <div className="max-w-2xl mx-auto">
            <div className="flex items-center justify-center mb-6">
              <div className="bg-gray-100/80 p-1 rounded-xl flex space-x-1 border border-gray-200/60 shadow-inner">
                <button onClick={() => setProcessingMode('local')} className={`flex items-center px-4 py-2 rounded-lg text-sm font-semibold ${processingMode === 'local' ? 'bg-white text-gray-900 shadow-sm border border-gray-200/50' : 'text-gray-500 hover:text-gray-700'}`}><Cpu className={`w-4 h-4 mr-2 ${processingMode === 'local' ? 'text-blue-600' : ''}`} /> Local Engine</button>
                <button onClick={() => setProcessingMode('llm')} className={`flex items-center px-4 py-2 rounded-lg text-sm font-semibold ${processingMode === 'llm' ? 'bg-white text-gray-900 shadow-sm border border-gray-200/50' : 'text-gray-500 hover:text-gray-700'}`}><Sparkles className={`w-4 h-4 mr-2 ${processingMode === 'llm' ? 'text-indigo-600' : ''}`} /> DeepSeek LLM</button>
              </div>
            </div>
            <label onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }} onDragLeave={() => setIsDragging(false)} onDrop={handleDrop} className={`flex flex-col items-center justify-center w-full h-40 border-2 border-dashed rounded-2xl cursor-pointer transition-all ${isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-gray-50 hover:bg-gray-100'}`}>
              <UploadCloud className={`w-8 h-8 mb-3 ${isDragging ? 'text-blue-500' : 'text-gray-400'}`} />
              <span className="text-sm font-medium text-gray-700">Add Document to Project</span>
              <span className="text-xs text-gray-400 mt-1">Using {processingMode === 'local' ? 'deterministic NLP (Faster)' : 'generative AI (Smarter)'}</span>
              <input type="file" className="hidden" onChange={(e) => handleUpload(e.target.files[0], processingMode)} />
            </label>
          </div>
        </>
      ) : (
        <div className="space-y-6">
          {contradictions.length === 0 ? (
             <div className="p-12 text-center text-emerald-600 bg-emerald-50 rounded-2xl border border-emerald-200">
               <CheckCircle2 className="w-12 h-12 mx-auto mb-3" />
               <h3 className="text-lg font-bold">No Contradictions Detected</h3>
               <p className="text-sm opacity-80">All documents in this project appear to be aligned.</p>
             </div>
          ) : (
            contradictions.map((c, i) => (
              <div key={i} className="bg-white rounded-2xl p-6 shadow-sm border border-gray-200">
                <div className="flex items-center mb-4">
                  <AlertTriangle className="w-5 h-5 text-rose-500 mr-2" />
                  <h3 className="font-bold text-gray-900 text-lg">{c.title}</h3>
                </div>
                <p className="text-gray-600 text-sm mb-6 leading-relaxed">{c.description}</p>
                
                {/* The Required "Side-by-Side" view */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-rose-50 border border-rose-100 p-4 rounded-xl">
                    <p className="text-[10px] font-bold text-rose-800 uppercase tracking-wider mb-2">{c.doc1_name}</p>
                    <p className="text-lg font-bold text-rose-900">{c.doc1_value}</p>
                  </div>
                  <div className="bg-rose-50 border border-rose-100 p-4 rounded-xl">
                    <p className="text-[10px] font-bold text-rose-800 uppercase tracking-wider mb-2">{c.doc2_name}</p>
                    <p className="text-lg font-bold text-rose-900">{c.doc2_value}</p>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}