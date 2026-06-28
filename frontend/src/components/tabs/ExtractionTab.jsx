import React from 'react';
import { 
  CheckCircle2, XCircle, FileSearch, Building2, User, 
  Target, CalendarDays, Briefcase, ListChecks, PieChart,
  Shield, Scale, FileSignature, RefreshCw, Users,
  DollarSign, LineChart, Landmark, Activity
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
    let present = extraction.clauses?.filter(c => c.status === 'present' || c.present === true) || [];
    let missing = extraction.clauses?.filter(c => c.status === 'missing' || c.present === false) || [];
    let waived = extraction.clauses?.filter(c => c.status === 'explicitly_waived') || [];

    if (filter) {
      const f = filter.toLowerCase();
      present = present.filter(c => c.clause_type.toLowerCase().includes(f) || (c.value && c.value.toLowerCase().includes(f)));
    }

    return (
      <div className="max-w-3xl mx-auto space-y-8 pb-12">
        
        {/* Top-Level Metadata Banner */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {doc_type === 'nda' && extraction.mutual !== null && (
            <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm flex flex-col justify-center">
              <div className="flex items-center text-gray-500 mb-1.5"><Users className="w-4 h-4 mr-1.5" /><span className="text-xs font-bold uppercase tracking-wider">NDA Type</span></div>
              <p className="text-sm font-bold text-gray-900">{extraction.mutual ? 'Mutual / Bilateral' : 'One-Way / Unilateral'}</p>
            </div>
          )}
          
          {extraction.governing_law && (
            <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm flex flex-col justify-center">
              <div className="flex items-center text-gray-500 mb-1.5"><Scale className="w-4 h-4 mr-1.5" /><span className="text-xs font-bold uppercase tracking-wider">Governing Law</span></div>
              <p className="text-sm font-bold text-gray-900">{extraction.governing_law}</p>
            </div>
          )}
          
          {extraction.contract_term && (
            <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm flex flex-col justify-center">
              <div className="flex items-center text-gray-500 mb-1.5"><CalendarDays className="w-4 h-4 mr-1.5" /><span className="text-xs font-bold uppercase tracking-wider">Term</span></div>
              <p className="text-sm font-bold text-gray-900">{extraction.contract_term}</p>
            </div>
          )}

          {extraction.signed !== null && extraction.signed !== undefined && (
            <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm flex flex-col justify-center">
              <div className="flex items-center text-gray-500 mb-1.5"><FileSignature className="w-4 h-4 mr-1.5" /><span className="text-xs font-bold uppercase tracking-wider">Execution</span></div>
              <p className={`text-sm font-bold ${extraction.signed ? 'text-emerald-600' : 'text-amber-600'}`}>
                {extraction.signed ? 'Signed' : 'Unsigned'}
              </p>
            </div>
          )}
        </div>

        {/* Existing Clauses Section */}
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
  // LAYOUT 4: FINANCIAL STATEMENTS
  // ---------------------------------------------------------
  if (doc_type === 'financial_statement') {
    
    // Helper to format currency/numbers beautifully
    const formatVal = (val, isPct = false) => {
      if (val === null || val === undefined) return '-';
      let formatted = Number(val).toLocaleString();
      if (isPct) return `${val}%`;
      return val < 0 ? `-$${Math.abs(val).toLocaleString()}` : `$${formatted}`;
    };

    const MetricRow = ({ label, value, isPct = false, bold = false }) => (
      <div className={`flex justify-between items-center py-2 border-b border-gray-50 last:border-0 ${bold ? 'font-bold text-gray-900' : 'text-gray-600'}`}>
        <span className="text-sm">{label}</span>
        <span className="text-sm">{formatVal(value, isPct)}</span>
      </div>
    );

    return (
      <div className="max-w-4xl mx-auto space-y-6 pb-12">
        
        {/* Header Block */}
        <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-gray-900 leading-tight">
              {extraction.entity_name ? extraction.entity_name.replace(/\n.*/g, '') : 'Unknown Entity'}
            </h2>
            <p className="text-sm text-gray-500 mt-1">{extraction.reporting_period || 'Reporting Period Not Specified'}</p>
          </div>
          <div className="flex gap-3">
             {extraction.currency && (
               <span className="px-3 py-1 bg-emerald-50 text-emerald-700 text-xs font-bold rounded-md uppercase tracking-wider border border-emerald-100">
                 {extraction.currency} {extraction.unit ? `(${extraction.unit})` : ''}
               </span>
             )}
             <span className="px-3 py-1 bg-blue-50 text-blue-700 text-xs font-bold rounded-md uppercase tracking-wider border border-blue-100">
               {extraction.statement_type?.replace('_', ' ')}
             </span>
          </div>
        </div>

        {/* Financial Data Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          
          {/* Income Statement */}
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden flex flex-col">
            <div className="px-5 py-4 border-b border-gray-100 bg-gray-50 flex items-center">
              <DollarSign className="w-4 h-4 text-emerald-600 mr-2" />
              <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider">Income Statement</h3>
            </div>
            <div className="p-5 flex-1 flex flex-col justify-between">
              <div>
                <MetricRow label="Revenue" value={extraction.income_statement?.revenue} bold />
                <MetricRow label="Cost of Goods Sold" value={extraction.income_statement?.cost_of_goods_sold} />
                <MetricRow label="Gross Profit" value={extraction.income_statement?.gross_profit} bold />
                <MetricRow label="Operating Expenses" value={extraction.income_statement?.operating_expenses} />
                <MetricRow label="EBITDA" value={extraction.income_statement?.ebitda} />
                <MetricRow label="EBIT (Operating Income)" value={extraction.income_statement?.ebit} />
                <MetricRow label="Interest Expense" value={extraction.income_statement?.interest_expense} />
                <MetricRow label="Tax Expense" value={extraction.income_statement?.tax_expense} />
              </div>
              <div className="mt-4 pt-4 border-t border-gray-200">
                <MetricRow label="Net Income" value={extraction.income_statement?.net_income} bold />
              </div>
            </div>
          </div>

          {/* Balance Sheet */}
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden flex flex-col">
            <div className="px-5 py-4 border-b border-gray-100 bg-gray-50 flex items-center">
              <Landmark className="w-4 h-4 text-indigo-600 mr-2" />
              <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider">Balance Sheet</h3>
            </div>
            <div className="p-5 flex-1 flex flex-col justify-between">
              <div>
                <MetricRow label="Total Assets" value={extraction.balance_sheet?.total_assets} bold />
                <MetricRow label="Current Assets" value={extraction.balance_sheet?.current_assets} />
                <MetricRow label="Cash & Equivalents" value={extraction.balance_sheet?.cash_and_equivalents} />
                <MetricRow label="Accounts Receivable" value={extraction.balance_sheet?.accounts_receivable} />
                <MetricRow label="Inventory" value={extraction.balance_sheet?.inventory} />
                <div className="my-3 border-b border-dashed border-gray-200"></div>
                <MetricRow label="Total Liabilities" value={extraction.balance_sheet?.total_liabilities} bold />
                <MetricRow label="Current Liabilities" value={extraction.balance_sheet?.current_liabilities} />
                <MetricRow label="Accounts Payable" value={extraction.balance_sheet?.accounts_payable} />
                <MetricRow label="Long Term Debt" value={extraction.balance_sheet?.long_term_debt} />
              </div>
              <div className="mt-4 pt-4 border-t border-gray-200">
                <MetricRow label="Total Equity" value={extraction.balance_sheet?.total_equity} bold />
                <MetricRow label="Retained Earnings" value={extraction.balance_sheet?.retained_earnings} />
              </div>
            </div>
          </div>

          {/* Cash Flow */}
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100 bg-gray-50 flex items-center">
              <Activity className="w-4 h-4 text-blue-500 mr-2" />
              <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider">Cash Flow</h3>
            </div>
            <div className="p-5">
              <MetricRow label="Operating Cash Flow" value={extraction.cash_flow?.operating_cash_flow} bold />
              <MetricRow label="Investing Cash Flow" value={extraction.cash_flow?.investing_cash_flow} />
              <MetricRow label="Financing Cash Flow" value={extraction.cash_flow?.financing_cash_flow} />
              <div className="mt-3 pt-3 border-t border-gray-200">
                <MetricRow label="Free Cash Flow" value={extraction.cash_flow?.free_cash_flow} bold />
                <MetricRow label="Capital Expenditures" value={extraction.cash_flow?.capital_expenditures} />
              </div>
            </div>
          </div>

          {/* Financial Ratios */}
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100 bg-gray-50 flex items-center">
              <LineChart className="w-4 h-4 text-rose-500 mr-2" />
              <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider">Key Ratios</h3>
            </div>
            <div className="p-5">
              <MetricRow label="Gross Margin" value={extraction.ratios?.gross_margin_pct} isPct bold />
              <MetricRow label="Net Margin" value={extraction.ratios?.net_margin_pct} isPct bold />
              <MetricRow label="Current Ratio" value={extraction.ratios?.current_ratio} />
              <MetricRow label="Debt to Equity" value={extraction.ratios?.debt_to_equity} />
              <MetricRow label="Return on Equity (ROE)" value={extraction.ratios?.return_on_equity_pct} isPct />
              <MetricRow label="Return on Assets (ROA)" value={extraction.ratios?.return_on_assets_pct} isPct />
            </div>
          </div>

        </div>
      </div>
    );
  }

  // ---------------------------------------------------------
  // LAYOUT 5: FALLBACK (Other)
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