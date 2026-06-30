import React from 'react';
import { ShieldAlert, FileText, Clock, ScanText, HardDrive } from 'lucide-react';

export default function OverviewTab({ doc }) {
  const cData = doc.stages.classification?.data || {};
  const eData = doc.stages.extraction?.data || {};
  const iData = doc.stages.ingestion?.data || {};
  
  const type = cData.document_type?.replace('_', ' ') || 'Document';
  const processingTime = eData.processing_time ? `${eData.processing_time}s` : 'Unknown';

  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      
      {/* Top Identity Block */}
      <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-200 flex justify-between items-center">
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-gray-400 mb-1">Identified As</p>
          <h2 className="text-2xl font-bold text-gray-900 capitalize">{type}</h2>
        </div>
      </div>

      {/* AI Summary */}
      {cData.document_summary && (
        <div className="bg-blue-50/50 p-5 rounded-2xl shadow-sm border border-blue-100">
          <h3 className="text-xs font-bold text-blue-800 uppercase tracking-wider mb-2">AI Summary</h3>
          <p className="text-sm text-blue-900 leading-relaxed font-medium">{cData.document_summary}</p>
        </div>
      )}

      {/* Metadata Info Card */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
          <FileText className="w-4 h-4 text-gray-400 mb-2" />
          <p className="text-xs text-gray-500 mb-0.5">Pages</p>
          <p className="text-sm font-bold text-gray-900">{iData.pages_count || 1}</p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
          <ScanText className="w-4 h-4 text-gray-400 mb-2" />
          <p className="text-xs text-gray-500 mb-0.5">Extraction Method</p>
          <p className="text-sm font-bold text-gray-900">{iData.ocr_used ? 'OCR (Scanned)' : 'Native Digital'}</p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
          <Clock className="w-4 h-4 text-gray-400 mb-2" />
          <p className="text-xs text-gray-500 mb-0.5">Processing Time</p>
          <p className="text-sm font-bold text-gray-900">{processingTime}</p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
          <HardDrive className="w-4 h-4 text-gray-400 mb-2" />
          <p className="text-xs text-gray-500 mb-0.5">File Size</p>
          <p className="text-sm font-bold text-gray-900">{(doc.size / 1024 / 1024).toFixed(2)} MB</p>
        </div>
      </div>
      
    </div>
  );
}