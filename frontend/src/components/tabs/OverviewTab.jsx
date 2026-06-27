import React from 'react';
import { ShieldAlert, Users, Calendar, Gavel } from 'lucide-react';

export default function OverviewTab({ doc }) {
  const cData = doc.stages.classification?.data || {};
  const type = cData.document_type?.replace('_', ' ') || 'Document';

  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      
      {/* Top Identity Block */}
      <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-200 flex justify-between items-center">
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-gray-400 mb-1">Identified As</p>
          <h2 className="text-2xl font-bold text-gray-900 capitalize">{type}</h2>
        </div>
        
        {/* Mock Risk Score Stub */}
        <div className="text-right">
          <div className="inline-flex items-center px-3 py-1 bg-amber-50 text-amber-700 rounded-full border border-amber-200 mb-1">
            <ShieldAlert className="w-4 h-4 mr-1.5" /> 
            <span className="text-sm font-semibold">Medium Risk</span>
          </div>
          <p className="text-xs text-gray-500">Requires standard review</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* Parties Summary */}
        <div className="bg-white p-5 rounded-2xl shadow-sm border border-gray-200">
          <div className="flex items-center text-gray-400 mb-3"><Users className="w-4 h-4 mr-2" /><span className="text-xs font-bold uppercase tracking-wider">Parties Involved</span></div>
          {cData.primary_parties?.length > 0 ? (
            <div className="space-y-2">
              {cData.primary_parties.map((p, i) => (
                <div key={i} className="text-sm font-medium text-gray-900">{p.name} <span className="text-gray-400 font-normal">({p.role})</span></div>
              ))}
            </div>
          ) : <span className="text-sm text-gray-500">None detected</span>}
        </div>

        {/* Dates Summary */}
        <div className="bg-white p-5 rounded-2xl shadow-sm border border-gray-200">
          <div className="flex items-center text-gray-400 mb-3"><Calendar className="w-4 h-4 mr-2" /><span className="text-xs font-bold uppercase tracking-wider">Key Dates</span></div>
          {cData.dates?.slice(0,2).map((d, i) => (
            <div key={i} className="mb-2">
              <span className="text-xs text-gray-500 block">{d.label}</span>
              <span className="text-sm font-medium text-gray-900">{d.value}</span>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
}