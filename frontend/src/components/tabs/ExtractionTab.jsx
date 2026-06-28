import React from 'react';
import { 
  CheckCircle2, XCircle, FileSearch, Building2, User, 
  Target, CalendarDays, Briefcase, ListChecks, PieChart 
} from 'lucide-react';

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

  // ---------------------------------------------------------
  // LAYOUT 1: CONTRACTS & NDAs
  // ---------------------------------------------------------
  if (doc_type === 'contract' || doc_type === 'nda') {
    let present = extraction.clauses?.filter(c => c.status === 'present') || [];
    let missing = extraction.clauses?.filter(c => c.status === 'missing') || [];
    let waived = extraction.clauses?.filter(c => c.status === 'explicitly_waived') || [];

    if (filter) {
      const f = filter.toLowerCase();
      present = present.filter(c => c.clause_type.toLowerCase().includes(f) || (c.value && c.value.toLowerCase().includes(f)));
    }

    return (
      <div className="max-w-3xl mx-auto space-y-8 pb-12">
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
                <div className="text-sm text-gray-800 bg-gray-50 p-3 rounded-lg border border-gray-100 whitespace-pre-wrap">
                  {c.value}
                </div>
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

        {waived.length > 0 && (
          <div className="mt-6">
            <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider mb-4 border-b pb-2">Explicitly Waived Clauses</h3>
            <div className="flex flex-wrap gap-2">
              {waived.map((c, i) => (
                <div key={i} className="inline-flex items-center bg-gray-50 border border-gray-200 px-3 py-1.5 rounded-lg text-sm text-gray-500 shadow-sm">
                  <span className="w-2 h-2 rounded-full bg-gray-400 mr-2"></span>
                  <span className="capitalize line-through opacity-70">{c.clause_type.replace(/_/g, ' ')}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  // ---------------------------------------------------------
  // LAYOUT 2: INVOICES
  // ---------------------------------------------------------
  if (doc_type === 'invoice') {
    return (
      <div className="max-w-3xl mx-auto space-y-6 pb-12">
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3 flex items-center">
              <Building2 className="w-4 h-4 mr-1.5" /> Vendor
            </h3>
            <p className="font-bold text-gray-900 text-lg mb-1">{extraction.vendor?.name || 'Unknown Vendor'}</p>
            {extraction.vendor?.address && <p className="text-sm text-gray-600">{extraction.vendor.address}</p>}
          </div>

          <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3 flex items-center">
              <User className="w-4 h-4 mr-1.5" /> Billed To
            </h3>
            <p className="font-bold text-gray-900 text-lg mb-1">{extraction.bill_to?.name || 'Unknown Client'}</p>
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm flex flex-wrap gap-x-8 gap-y-4">
          <div>
            <p className="text-xs text-gray-500 uppercase font-semibold">Invoice Number</p>
            <p className="text-sm font-bold text-gray-900">{extraction.invoice_number || '-'}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase font-semibold">Date Issued</p>
            <p className="text-sm font-bold text-gray-900">{extraction.invoice_date || '-'}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase font-semibold">Due Date</p>
            <p className="text-sm font-bold text-rose-600">{extraction.due_date || '-'}</p>
          </div>
        </div>

        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
              <tr>
                <th className="px-4 py-3 font-semibold">Description</th>
                <th className="px-4 py-3 font-semibold text-right">Qty</th>
                <th className="px-4 py-3 font-semibold text-right">Price</th>
                <th className="px-4 py-3 font-semibold text-right">Total</th>
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
        
        <div className="flex justify-end">
          <div className="w-72 space-y-3 p-5 bg-white rounded-xl border border-gray-200 shadow-sm">
            <div className="flex justify-between text-sm text-gray-600">
              <span>Subtotal</span>
              <span>{extraction.currency || ''} {extraction.subtotal?.toLocaleString() || '-'}</span>
            </div>
            <div className="flex justify-between text-sm text-gray-600">
              <span>Tax</span>
              <span>{extraction.currency || ''} {extraction.tax_amount?.toLocaleString() || '-'}</span>
            </div>
            <div className="pt-3 border-t border-gray-200 flex justify-between text-lg font-bold text-gray-900">
              <span>Total Due</span>
              <span>{extraction.currency || ''} {extraction.total_amount?.toLocaleString() || '-'}</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------
  // LAYOUT 3: RFPs
  // ---------------------------------------------------------
  if (doc_type === 'rfp') {
    return (
      <div className="max-w-3xl mx-auto space-y-6 pb-12">
        
        {/* RFP Header & Scope */}
        <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-gray-900 leading-tight">
              {extraction.rfp_title || 'Untitled RFP'}
            </h2>
            {extraction.rfp_number && (
              <span className="px-3 py-1 bg-gray-100 text-gray-700 text-xs font-bold rounded-md uppercase tracking-wider">
                {extraction.rfp_number}
              </span>
            )}
          </div>
          
          <div className="flex items-center text-sm text-gray-600 mb-6">
            <Building2 className="w-4 h-4 mr-2 text-gray-400" />
            <span className="font-medium text-gray-900 mr-2">Issuing Org:</span>
            {extraction.issuing_organisation || 'Not specified'}
          </div>

          <div className="bg-blue-50/50 p-4 rounded-xl border border-blue-100">
            <h3 className="text-xs font-bold text-blue-800 uppercase tracking-wider mb-2 flex items-center">
              <Target className="w-4 h-4 mr-1.5" /> Scope of Work
            </h3>
            <p className="text-sm text-blue-900 leading-relaxed">
              {extraction.scope_of_work || 'Scope of work not detailed.'}
            </p>
          </div>
        </div>

        {/* Key Dates Timeline Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: 'Issue Date', value: extraction.issue_date },
            { label: 'Q&A Deadline', value: extraction.qa_deadline },
            { label: 'Submission', value: extraction.submission_deadline, highlight: true },
            { label: 'Award Date', value: extraction.award_date }
          ].map((date, idx) => (
            <div key={idx} className={`p-4 rounded-xl border shadow-sm ${date.highlight ? 'bg-indigo-50 border-indigo-200' : 'bg-white border-gray-200'}`}>
              <CalendarDays className={`w-4 h-4 mb-2 ${date.highlight ? 'text-indigo-600' : 'text-gray-400'}`} />
              <p className={`text-xs font-bold uppercase tracking-wider mb-1 ${date.highlight ? 'text-indigo-800' : 'text-gray-500'}`}>
                {date.label}
              </p>
              <p className={`text-sm font-semibold ${date.highlight ? 'text-indigo-900' : 'text-gray-900'}`}>
                {date.value || '-'}
              </p>
            </div>
          ))}
        </div>

        {/* Financials & Logistics */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm flex items-start space-x-3">
            <Briefcase className="w-5 h-5 text-emerald-600 mt-0.5" />
            <div>
              <p className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-1">Contract Value & Term</p>
              <p className="text-sm font-semibold text-gray-900">{extraction.contract_value || 'Value not specified'}</p>
              <p className="text-sm text-gray-500 mt-1">{extraction.contract_duration || 'Duration not specified'}</p>
            </div>
          </div>
          <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm flex items-start space-x-3">
            <User className="w-5 h-5 text-blue-600 mt-0.5" />
            <div>
              <p className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-1">Point of Contact</p>
              <p className="text-sm font-semibold text-gray-900">{extraction.contact?.name || 'No specific contact'}</p>
              {extraction.contact?.email && <p className="text-sm text-gray-500">{extraction.contact.email}</p>}
            </div>
          </div>
        </div>

        {/* Requirements Table */}
        {extraction.requirements?.length > 0 && (
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100 bg-gray-50 flex items-center">
              <ListChecks className="w-4 h-4 text-gray-500 mr-2" />
              <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider">Requirements</h3>
            </div>
            <ul className="divide-y divide-gray-100">
              {extraction.requirements.map((req, idx) => (
                <li key={idx} className="p-4 flex items-start space-x-3 hover:bg-gray-50/50">
                  <div className="mt-0.5">
                    {req.mandatory 
                      ? <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                      : <div className="w-4 h-4 rounded-full border-2 border-gray-300" />
                    }
                  </div>
                  <div className="flex-1">
                    <p className="text-sm text-gray-900 font-medium">{req.description}</p>
                    <span className="inline-block mt-1.5 px-2 py-0.5 bg-gray-100 text-gray-600 text-[10px] font-bold uppercase tracking-wider rounded">
                      {req.category}
                    </span>
                  </div>
                  {req.mandatory && (
                    <span className="px-2 py-1 bg-rose-50 text-rose-700 text-[10px] font-bold uppercase tracking-wider rounded">
                      Mandatory
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Evaluation Criteria */}
        {extraction.evaluation_criteria?.length > 0 && (
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden p-5">
            <div className="flex items-center mb-4">
              <PieChart className="w-4 h-4 text-gray-500 mr-2" />
              <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider">Evaluation Criteria</h3>
            </div>
            <div className="space-y-4">
              {extraction.evaluation_criteria.map((crit, idx) => (
                <div key={idx}>
                  <div className="flex justify-between text-sm font-medium mb-1.5">
                    <span className="text-gray-900">{crit.criterion}</span>
                    <span className="text-gray-500">{crit.weight_pct}%</span>
                  </div>
                  <div className="w-full bg-gray-100 rounded-full h-2">
                    <div 
                      className="bg-indigo-500 h-2 rounded-full" 
                      style={{ width: `${crit.weight_pct || 0}%` }}
                    ></div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  // ---------------------------------------------------------
  // LAYOUT 4: FALLBACK (Financial Statements, Other)
  // ---------------------------------------------------------
  return (
    <div className="max-w-3xl mx-auto pb-12">
      <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider mb-4 border-b pb-2">Raw Extraction Data</h3>
      <pre className="text-xs font-mono text-gray-700 bg-white p-4 rounded-xl shadow-sm border border-gray-200 overflow-auto">
        {JSON.stringify(extraction, null, 2)}
      </pre>
    </div>
  );
}