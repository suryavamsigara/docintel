import React from 'react';
import { CheckCircle2, XCircle, FileSearch } from 'lucide-react';

export default function ExtractionTab({ data, onJump, filter }) {
  if (!data) return null;
  const { doc_type, extraction } = data;

  const PageBadge = ({ page }) => {
    if (!page) return null;
    return (
      <button 
        onClick={() => onJump(page)}
        className="ml-3 inline-flex items-center text-xs font-semibold text-indigo-600 bg-indigo-50 hover:bg-indigo-100 px-2 py-0.5 rounded transition-colors"
      >
        <FileSearch className="w-3 h-3 mr-1" /> Page {page}
      </button>
    );
  };

  if (doc_type === 'contract' || doc_type === 'nda') {
    let present = extraction.clauses?.filter(c => c.present) || [];
    let missing = extraction.clauses?.filter(c => !c.present) || [];

    if (filter) {
      const f = filter.toLowerCase();
      present = present.filter(c => c.clause_type.toLowerCase().includes(f) || (c.value && c.value.toLowerCase().includes(f)));
    }

    return (
      <div className="max-w-2xl mx-auto space-y-8">
        <div>
          <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider mb-4 border-b pb-2">Identified Clauses</h3>
          <div className="space-y-3">
            {present.map((c, i) => (
              <div key={i} className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm group">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center">
                    <CheckCircle2 className="w-4 h-4 text-emerald-500 mr-2" />
                    <span className="font-semibold text-gray-900 capitalize">{c.clause_type.replace(/_/g, ' ')}</span>
                  </div>
                  <PageBadge page={c.page} />
                </div>
                <div className="text-sm text-gray-800 bg-gray-50 p-3 rounded-lg border border-gray-100">{c.value}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return <pre className="text-xs">...</pre>; // Fallbacks
}