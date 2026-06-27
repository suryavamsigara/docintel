import React, { useState } from 'react';
import { FileText, UploadCloud, Loader2, CheckCircle2, ChevronRight } from 'lucide-react';

export default function ProjectDetail({ project, documents, onUpload, onOpenDoc }) {
  const [isDragging, setIsDragging] = useState(false);

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files?.length) onUpload(e.dataTransfer.files[0]);
  };

  return (
    <div className="max-w-5xl mx-auto p-8">
      <h1 className="text-3xl font-bold tracking-tight mb-8">{project.name}</h1>

      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden mb-8">
        {documents.length === 0 ? (
          <div className="p-12 text-center text-gray-500">No documents in this project yet.</div>
        ) : (
          <div className="divide-y divide-gray-100">
            {documents.map(doc => (
              <button 
                key={doc.id} 
                onClick={() => onOpenDoc(doc.id)}
                className="w-full text-left p-4 hover:bg-gray-50 flex items-center justify-between transition-colors group"
              >
                <div className="flex items-center space-x-4">
                  <FileText className="w-8 h-8 text-blue-500 p-1.5 bg-blue-50 rounded-lg" />
                  <div>
                    <h4 className="font-medium text-gray-900">{doc.name}</h4>
                    <p className="text-xs text-gray-500">{(doc.size / 1024 / 1024).toFixed(2)} MB</p>
                  </div>
                </div>
                
                <div className="flex items-center space-x-4">
                  {doc.status === 'processing' ? (
                    <span className="flex items-center text-xs font-medium text-amber-600 bg-amber-50 px-3 py-1 rounded-full border border-amber-200">
                      <Loader2 className="w-3 h-3 mr-1.5 animate-spin" /> Processing
                    </span>
                  ) : (
                    <span className="flex items-center text-xs font-medium text-emerald-700 bg-emerald-50 px-3 py-1 rounded-full border border-emerald-200">
                      <CheckCircle2 className="w-3 h-3 mr-1.5" /> Analyzed
                    </span>
                  )}
                  <ChevronRight className="w-5 h-5 text-gray-300 group-hover:text-blue-500 transition-colors" />
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      <label 
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        className={`flex flex-col items-center justify-center w-full h-40 border-2 border-dashed rounded-2xl cursor-pointer transition-all ${
          isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-gray-50 hover:bg-gray-100'
        }`}
      >
        <UploadCloud className={`w-8 h-8 mb-3 ${isDragging ? 'text-blue-500' : 'text-gray-400'}`} />
        <span className="text-sm font-medium text-gray-700">Add Document to Project</span>
        <input type="file" className="hidden" onChange={(e) => onUpload(e.target.files[0])} />
      </label>
    </div>
  );
}