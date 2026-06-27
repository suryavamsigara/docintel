import React from 'react';
import { CheckCircle2, XCircle } from 'lucide-react';

export default function ExtractionTab({ data }) {
  if (!data) return null;
  const { doc_type, extraction } = data;

  if (doc_type === 'contract' || doc_type === 'nda') {
    const present = extraction.clauses?.filter(c => c.present) || [];
    const missing = extraction.clauses?.filter(c => !c.present) || [];

    return (
      <div className="max-w-2xl mx-auto space-y-8">
        <div>
          <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider mb-4 border-b pb-2">Identified Clauses</h3>
          <div className="space-y-3">
            {present.map((c, i) => (
              <div key={i} className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
                <div className="flex items-center mb-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500 mr-2" />
                  <span className="font-semibold text-gray-900 capitalize">{c.clause_type.replace(/_/g, ' ')}</span>
                </div>
                <div className="text-sm text-gray-800 bg-gray-50 p-3 rounded-lg border border-gray-100">{c.value}</div>
              </div>
            ))}
          </div>
        </div>

        {missing.length > 0 && (
          <div>
            <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider mb-4 border-b pb-2">Missing Standard Clauses</h3>
            <div className="flex flex-wrap gap-2">
              {missing.map((c, i) => (
                <div key={i} className="inline-flex items-center bg-white border border-gray-200 px-3 py-1.5 rounded-lg text-sm text-gray-500 shadow-sm">
                  <XCircle className="w-4 h-4 mr-2 opacity-40" />
                  <span className="capitalize">{c.clause_type.replace(/_/g, ' ')}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  // Fallback for invoice/other (You can plug in the Invoice Table UI from previous response here)
  return (
    <pre className="text-xs font-mono text-gray-700 bg-white p-4 rounded-xl shadow-sm border border-gray-200">
      {JSON.stringify(extraction, null, 2)}
    </pre>
  );
}