import React from 'react';
import { FileText, Users, MapPin, Calendar, CheckCircle2, XCircle, FileSignature, Receipt, ChevronRight } from 'lucide-react';

// --- CLASSIFICATION UI ---
export function ClassificationView({ data }) {
  if (!data) return null;

  const getDocIcon = (type) => {
    if (type === 'contract' || type === 'nda') return <FileSignature className="w-5 h-5 text-indigo-500" />;
    if (type === 'invoice') return <Receipt className="w-5 h-5 text-emerald-500" />;
    return <FileText className="w-5 h-5 text-blue-500" />;
  };

  return (
    <div className="space-y-4 pt-2">
      <div className="grid grid-cols-2 gap-3">
        {/* Doc Type Card */}
        <div className="p-3 bg-white rounded-xl border border-gray-200 shadow-sm flex items-center space-x-3">
          <div className="p-2 bg-gray-50 rounded-lg">{getDocIcon(data.document_type)}</div>
          <div>
            <p className="text-xs text-gray-500 font-medium uppercase tracking-wider">Document Type</p>
            <p className="text-sm font-semibold text-gray-900 capitalize">{data.document_type?.replace('_', ' ')}</p>
          </div>
        </div>

        {/* Jurisdiction Card */}
        {data.jurisdiction && (
          <div className="p-3 bg-white rounded-xl border border-gray-200 shadow-sm flex items-center space-x-3">
            <div className="p-2 bg-gray-50 rounded-lg"><MapPin className="w-5 h-5 text-rose-500" /></div>
            <div>
              <p className="text-xs text-gray-500 font-medium uppercase tracking-wider">Jurisdiction</p>
              <p className="text-sm font-semibold text-gray-900">{data.jurisdiction.value}</p>
            </div>
          </div>
        )}
      </div>

      {/* Parties List */}
      {data.primary_parties?.length > 0 && (
        <div className="p-4 bg-gray-50/50 rounded-xl border border-gray-100">
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3 flex items-center"><Users className="w-4 h-4 mr-1.5" /> Primary Parties</h4>
          <div className="space-y-2">
            {data.primary_parties.map((p, idx) => (
              <div key={idx} className="flex justify-between items-center bg-white p-2.5 rounded-lg shadow-sm border border-gray-100">
                <span className="text-sm font-medium text-gray-900">{p.name}</span>
                <span className="text-xs px-2.5 py-1 bg-blue-50 text-blue-700 rounded-full font-medium">{p.role}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Dates Timeline */}
      {data.dates?.length > 0 && (
        <div className="p-4 bg-gray-50/50 rounded-xl border border-gray-100">
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3 flex items-center"><Calendar className="w-4 h-4 mr-1.5" /> Key Dates</h4>
          <div className="flex flex-wrap gap-2">
            {data.dates.map((d, idx) => (
              <div key={idx} className="inline-flex flex-col bg-white border border-gray-200 rounded-lg px-3 py-2 shadow-sm">
                <span className="text-[10px] text-gray-500 font-semibold uppercase">{d.label}</span>
                <span className="text-sm font-medium text-gray-900">{d.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}


// --- EXTRACTION UI (POLYMORPHIC) ---
export function ExtractionView({ data }) {
  if (!data || !data.extraction) return null;
  const { doc_type, extraction } = data;

  // Invoice Layout
  if (doc_type === 'invoice') {
    return (
      <div className="pt-3 space-y-4">
        {/* Line Items Table */}
        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
              <tr>
                <th className="px-4 py-3 font-medium">Description</th>
                <th className="px-4 py-3 font-medium text-right">Qty</th>
                <th className="px-4 py-3 font-medium text-right">Price</th>
                <th className="px-4 py-3 font-medium text-right">Total</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {extraction.line_items?.map((item, idx) => (
                <tr key={idx} className="hover:bg-gray-50/50">
                  <td className="px-4 py-3 font-medium text-gray-900">{item.description}</td>
                  <td className="px-4 py-3 text-right text-gray-600">{item.quantity || '-'}</td>
                  <td className="px-4 py-3 text-right text-gray-600">{item.unit_price?.toLocaleString() || '-'}</td>
                  <td className="px-4 py-3 text-right font-medium text-gray-900">{item.amount?.toLocaleString() || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        
        {/* Totals Block */}
        <div className="flex justify-end">
          <div className="w-64 space-y-2 p-4 bg-gray-50 rounded-xl border border-gray-200">
            <div className="flex justify-between text-sm text-gray-600">
              <span>Subtotal</span><span>{extraction.currency} {extraction.subtotal?.toLocaleString() || '-'}</span>
            </div>
            <div className="flex justify-between text-sm text-gray-600">
              <span>Tax</span><span>{extraction.currency} {extraction.tax_amount?.toLocaleString() || '-'}</span>
            </div>
            <div className="pt-2 border-t border-gray-200 flex justify-between text-base font-bold text-gray-900">
              <span>Total Due</span><span>{extraction.currency} {extraction.total_amount?.toLocaleString() || '-'}</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Contract/NDA Layout
  if (doc_type === 'contract' || doc_type === 'nda') {
    const presentClauses = extraction.clauses?.filter(c => c.present) || [];
    const missingClauses = extraction.clauses?.filter(c => !c.present) || [];

    return (
      <div className="pt-3 space-y-6">
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Extracted Clauses</h4>
          <div className="space-y-2">
            {presentClauses.map((c, idx) => (
              <details key={idx} className="group bg-white border border-emerald-100 rounded-xl shadow-sm overflow-hidden open:ring-1 open:ring-emerald-500/20">
                <summary className="flex items-center justify-between p-3 cursor-pointer hover:bg-gray-50 list-none">
                  <div className="flex items-center space-x-3">
                    <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                    <span className="text-sm font-semibold text-gray-900 capitalize">{c.clause_type.replace(/_/g, ' ')}</span>
                  </div>
                  <ChevronRight className="w-4 h-4 text-gray-400 transition-transform group-open:rotate-90" />
                </summary>
                <div className="p-4 bg-gray-50 border-t border-gray-100">
                  <p className="text-sm font-medium text-gray-900 mb-2">Extracted Value:</p>
                  <p className="text-sm text-indigo-700 bg-indigo-50 p-2.5 rounded-lg border border-indigo-100 mb-3">{c.value || 'Present'}</p>
                  {c.raw_text && (
                    <>
                      <p className="text-xs font-medium text-gray-500 mb-1">Source Text:</p>
                      <p className="text-xs text-gray-600 font-serif italic border-l-2 border-gray-300 pl-3">{c.raw_text}</p>
                    </>
                  )}
                </div>
              </details>
            ))}
          </div>
        </div>

        {missingClauses.length > 0 && (
          <div>
             <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Missing Standard Clauses</h4>
             <div className="flex flex-wrap gap-2">
               {missingClauses.map((c, idx) => (
                 <span key={idx} className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-500 border border-gray-200">
                   <XCircle className="w-3 h-3 mr-1.5 opacity-50" />
                   {c.clause_type.replace(/_/g, ' ')}
                 </span>
               ))}
             </div>
          </div>
        )}
      </div>
    );
  }

  // Fallback Raw JSON for unknown types
  return (
    <pre className="mt-3 text-xs text-gray-700 whitespace-pre-wrap font-mono p-3 bg-gray-50 rounded-xl border border-gray-200">
      {JSON.stringify(extraction, null, 2)}
    </pre>
  );
}