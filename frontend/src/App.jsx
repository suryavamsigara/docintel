import React, { useState } from 'react';
import { UploadCloud, FileText } from 'lucide-react';
import { usePipelineStream } from './hooks/usePipelineStream';
import PipelineStage from './components/PipelineStage';

export default function App() {
  const { pipelineState, connect, resetPipeline } = usePipelineStream();
  const [isDragging, setIsDragging] = useState(false);
  const [file, setFile] = useState(null);

  const handleUpload = async (uploadFile) => {
    setFile(uploadFile);
    resetPipeline();
    
    // Generate an ephemeral client ID for this specific document pipeline
    const newClientId = Math.random().toString(36).substring(7);
    connect(newClientId);

    const formData = new FormData();
    formData.append('file', uploadFile);

    try {
      await fetch(`http://localhost:8000/api/upload?client_id=${newClientId}`, {
        method: 'POST',
        body: formData,
      });
    } catch (err) {
      console.error('Upload failed:', err);
    }
  };

  const onDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleUpload(e.dataTransfer.files[0]);
    }
  };

  return (
    <div className="min-h-screen bg-ios-gray font-sans selection:bg-ios-blue selection:text-white pb-20">
      
      {/* Top Navigation Bar */}
      <nav className="bg-white/80 backdrop-blur-xl border-b border-gray-200 sticky top-0 z-50">
        <div className="max-w-4xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <FileText className="w-5 h-5 text-ios-blue" />
            <span className="font-semibold tracking-tight text-gray-900">Contract Intelligence</span>
          </div>
        </div>
      </nav>

      <main className="max-w-4xl mx-auto px-6 mt-8 grid grid-cols-1 md:grid-cols-12 gap-8">
        
        {/* Left Column: Upload Dropzone */}
        <div className="md:col-span-5">
          <div className="sticky top-24">
            <h2 className="text-2xl font-bold tracking-tight text-gray-900 mb-4">New Document</h2>
            
            <label 
              onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={onDrop}
              className={`flex flex-col items-center justify-center w-full h-64 border-2 border-dashed rounded-3xl cursor-pointer transition-all ${
                isDragging ? 'border-ios-blue bg-blue-50/50' : 'border-gray-300 bg-white hover:bg-gray-50'
              }`}
            >
              <div className="flex flex-col items-center justify-center pt-5 pb-6">
                <div className={`p-4 rounded-full mb-4 ${isDragging ? 'bg-ios-blue text-white' : 'bg-gray-100 text-gray-400'}`}>
                   <UploadCloud className="w-8 h-8" />
                </div>
                <p className="mb-2 text-sm text-gray-600 font-medium">Click to upload or drag & drop</p>
                <p className="text-xs text-gray-400">PDF, DOCX, XLSX, or Images</p>
              </div>
              <input 
                type="file" 
                className="hidden" 
                onChange={(e) => e.target.files && handleUpload(e.target.files[0])} 
                accept=".pdf,.docx,.xlsx,.xls,.jpg,.jpeg,.png"
              />
            </label>

            {file && (
              <div className="mt-6 p-4 bg-white rounded-2xl shadow-apple border border-gray-100 flex items-center space-x-3">
                 <FileText className="w-8 h-8 text-ios-blue p-1.5 bg-blue-50 rounded-lg" />
                 <div className="truncate flex-1">
                   <p className="text-sm font-semibold text-gray-900 truncate">{file.name}</p>
                   <p className="text-xs text-gray-500">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                 </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Real-Time Pipeline Viewer */}
        <div className="md:col-span-7">
          <h2 className="text-2xl font-bold tracking-tight text-gray-900 mb-4">Pipeline Status</h2>
          
          <div className="space-y-4">
            <PipelineStage 
              title="1. Ingestion & Normalisation" 
              description="Routing, structure preservation, and layout-aware text mapping." 
              state={pipelineState.ingestion} 
            />
            
            <PipelineStage 
              title="2. Document Classification" 
              description="Type detection, primary parties, and jurisdiction extraction." 
              state={pipelineState.classification} 
            />
            
            <PipelineStage 
              title="3. Entity & Clause Extraction" 
              description="Identifying targeted clauses, metadata, and financial specifics." 
              state={pipelineState.extraction} 
            />
            
            <PipelineStage 
              title="4. Anomaly Detection" 
              description="Flagging asymmetric clauses and unusual variables." 
              state={pipelineState.anomaly} 
            />
          </div>
        </div>

      </main>
    </div>
  );
}