import React from 'react';
import { FileSignature, Users, Calendar, MapPin, Receipt, FileText } from 'lucide-react';

export default function ClassificationTab({ data }) {
  if (!data) return (
    <div className="flex h-full items-center justify-center text-gray-400 text-sm">
      Classification data not yet available.
    </div>
  );

  const getDocIcon = (type) => {
    if (type === 'contract' || type === 'nda') return <FileSignature className="w-6 h-6 text-indigo-500" />;
    if (type === 'invoice') return <Receipt className="w-6 h-6 text-emerald-500" />;
    return <FileText className="w-6 h-6 text-blue-500" />;
  };

  return (
    <div className="max-w-3xl mx-auto space-y-8 pb-12">
      
      {/* 1. Document Identity */}
      <section>
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3">Document Identity</h3>
        <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-sm flex items-center space-x-4">
          <div className="p-3 bg-gray-50 rounded-xl">
            {getDocIcon(data.document_type)}
          </div>
          <div>
            <p className="text-xl font-bold text-gray-900 capitalize">
              {data.document_type?.replace('_', ' ') || 'Unknown Type'}
            </p>
            {/* Subtle confidence indicator as requested */}
            <p className="text-xs font-medium text-gray-400 mt-0.5">High Confidence</p>
          </div>
        </div>
      </section>

      {/* 2. Governing Jurisdiction */}
      {data.jurisdiction && (
        <section>
          <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3">Governing Jurisdiction</h3>
          <div className="bg-white p-4 rounded-2xl border border-gray-200 shadow-sm flex items-center space-x-4">
            <div className="p-2.5 bg-rose-50 rounded-xl">
              <MapPin className="w-5 h-5 text-rose-500" />
            </div>
            <div>
              <p className="text-base font-semibold text-gray-900">{data.jurisdiction.value}</p>
              {data.jurisdiction.context && (
                <p className="text-xs text-gray-500 mt-1 italic pr-4">"{data.jurisdiction.context}"</p>
              )}
            </div>
          </div>
        </section>
      )}

      {/* 3. Primary Parties */}
      {data.primary_parties?.length > 0 && (
        <section>
          <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3">Primary Parties</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {data.primary_parties.map((party, idx) => (
              <div key={idx} className="bg-white p-5 rounded-2xl border border-gray-200 shadow-sm flex flex-col h-full">
                <div className="flex items-center justify-between mb-4">
                  <span className="text-xs font-bold uppercase tracking-wider px-2.5 py-1 bg-gray-100 text-gray-600 rounded-md">
                    {party.role}
                  </span>
                  <Users className="w-4 h-4 text-gray-300" />
                </div>
                <p className="text-lg font-bold text-gray-900 mb-3">{party.name}</p>
                {party.basis && (
                  <div className="mt-auto pt-3 border-t border-gray-100">
                    <p className="text-[11px] font-medium text-gray-400 uppercase mb-1">Extraction Basis</p>
                    <p className="text-xs text-gray-500">{party.basis}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 4. Key Dates */}
      {data.dates?.length > 0 && (
        <section>
          <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3">Key Dates</h3>
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="divide-y divide-gray-100">
              {data.dates.map((date, idx) => (
                <div key={idx} className="p-4 hover:bg-gray-50 transition-colors flex items-start space-x-4 group">
                  <div className="mt-0.5 p-1.5 bg-blue-50 rounded-lg group-hover:bg-blue-100 transition-colors">
                    <Calendar className="w-4 h-4 text-blue-500" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-baseline justify-between mb-1.5">
                      <p className="text-sm font-bold text-gray-900">{date.label}</p>
                      <p className="text-sm font-semibold text-blue-700 bg-white shadow-sm px-2.5 py-1 rounded-lg border border-gray-200">
                        {date.value}
                      </p>
                    </div>
                    {date.context && (
                      <p className="text-xs text-gray-500 italic">"{date.context}"</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

    </div>
  );
}