import React, { useState } from 'react';
import { UploadCloud, FileText, Database } from 'lucide-react';
import { usePipelineStream } from './hooks/usePipelineStream';
import PipelineStage from './components/PipelineStage';

export default function App() {
  const { pipelineState, connect, resetPipeline } = usePipelineStream();
  const [isDragging, setIsDragging] = useState(false);
  const [file, setFile] = useState(null);

  const handleUpload = async (uploadFile) => {
    setFile(uploadFile);
    resetPipeline();
    const newClientId = Math.random().toString(36).substring(7);
    connect(newClientId);

    const formData = new FormData();
    formData.append('file', uploadFile);

    try {
      await fetch(`http://localhost:8000/api/upload?client_id=${newClientId}`, { method: 'POST', body: formData });
    } catch (err) { console.error('Upload failed:', err); }
  };

  const onDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files?.length > 0) handleUpload(e.dataTransfer.files[0]);
  };

  // Extract preview text from ingestion data if available
  const docPreview = pipelineState.ingestion.data?.preview_text;

  return (
    <div className="min-h-screen bg-[#F9FAFB] font-sans text-gray-900 selection:bg-indigo-500 selection:text-white">
      
      {/* Navbar */}
      <nav className="bg-white border-b border-gray-200 sticky top-0 z-50 shadow-sm">
        <div className="max-w-[1400px] mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="bg-indigo-600 p-1.5 rounded-lg text-white"><Database className="w-4 h-4" /></div>
            <span className="font-bold tracking-tight text-gray-900">Contract Intelligence</span>
          </div>
        </div>
      </nav>

      <main className="max-w-[1400px] mx-auto px-6 mt-6 grid grid-cols-1 lg:grid-cols-12 gap-8 h-[calc(100vh-6rem)]">
        
        {/* Left Column: Input & Document Preview */}
        <div className="lg:col-span-5 flex flex-col h-full space-y-4">
          
          {/* Upload Box */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-1">
            <label 
              onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={onDrop}
              className={`flex flex-col items-center justify-center w-full h-32 border-2 border-dashed rounded-xl cursor-pointer transition-all ${
                isDragging ? 'border-indigo-500 bg-indigo-50' : 'border-gray-200 bg-gray-50 hover:bg-gray-100'
              }`}
            >
              <div className="flex flex-col items-center justify-center text-center">
                 <p className="text-sm font-semibold text-gray-700">Upload a new document</p>
                 <p className="text-xs text-gray-500 mt-1">PDF, DOCX, XLSX, or Images</p>
              </div>
              <input type="file" className="hidden" onChange={(e) => handleUpload(e.target.files[0])} />
            </label>
          </div>

          {/* Document Viewer (Appears after upload) */}
          {file && (
            <div className="flex-1 bg-white rounded-2xl shadow-sm border border-gray-200 flex flex-col overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-100 bg-gray-50 flex items-center space-x-2">
                <FileText className="w-4 h-4 text-gray-400" />
                <span className="text-sm font-semibold text-gray-700 truncate">{file.name}</span>
              </div>
              <div className="flex-1 p-6 overflow-y-auto bg-[#FAFAFA] font-serif text-sm leading-relaxed text-gray-700">
                {docPreview ? (
                  <div className="whitespace-pre-wrap">{docPreview}</div>
                ) : (
                  <div className="h-full flex items-center justify-center text-gray-400 text-sm">
                    {pipelineState.ingestion.status === 'running' ? 'Extracting text...' : 'Waiting for document...'}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Intelligent Pipeline Feed */}
        <div className="lg:col-span-7 bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden flex flex-col">
          <div className="px-6 py-4 border-b border-gray-100 bg-gray-50 flex justify-between items-center">
            <h2 className="text-base font-bold tracking-tight text-gray-900">Analysis Pipeline</h2>
            {pipelineState.extraction.status === 'running' && (
               <span className="flex h-3 w-3 relative">
                 <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                 <span className="relative inline-flex rounded-full h-3 w-3 bg-indigo-500"></span>
               </span>
            )}
          </div>
          
          <div className="flex-1 overflow-y-auto p-6 bg-gray-50/30">
            {!file ? (
              <div className="h-full flex flex-col items-center justify-center text-gray-400 space-y-4">
                <UploadCloud className="w-12 h-12 opacity-20" />
                <p className="text-sm">Upload a document to begin processing.</p>
              </div>
            ) : (
              <div className="max-w-2xl mx-auto space-y-2">
                <PipelineStage 
                  stageKey="ingestion"
                  title="1. Ingestion & Normalisation" 
                  state={pipelineState.ingestion} 
                />
                <PipelineStage 
                  stageKey="classification"
                  title="2. Document Classification" 
                  state={pipelineState.classification} 
                />
                <PipelineStage 
                  stageKey="extraction"
                  title="3. Entity & Clause Extraction" 
                  state={pipelineState.extraction} 
                />
              </div>
            )}
          </div>
        </div>

      </main>
    </div>
  );
}