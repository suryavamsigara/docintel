import React from 'react';
// FIX: Added CheckCircle2 to the import list
import { AlertOctagon, AlertTriangle, Info, CheckCircle2 } from 'lucide-react';

export default function AnomaliesTab({ anomalyData, riskData, onJump }) {
  if (!anomalyData || !anomalyData.anomalies) return null;

  const anomalies = anomalyData.anomalies;
  const score = riskData?.overall_score || 0;
  const level = riskData?.risk_level || 'Unknown';

  const getSeverityConfig = (severity) => {
    switch (severity.toLowerCase()) {
      case 'critical': return { icon: <AlertOctagon className="w-5 h-5 text-rose-500 mt-0.5" />, bg: 'bg-rose-50', border: 'border-rose-200', text: 'text-rose-800' };
      case 'warning': return { icon: <AlertTriangle className="w-5 h-5 text-amber-500 mt-0.5" />, bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-800' };
      default: return { icon: <Info className="w-5 h-5 text-blue-500 mt-0.5" />, bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-800' };
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-8 pb-12">
      
      {/* Risk Summary Header */}
      <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 mb-1">Risk Assessment: {level}</h2>
          <p className="text-sm text-gray-500">{anomalies.length} deviations detected across the document.</p>
        </div>
        <div className="flex flex-col items-center">
          <div className="text-3xl font-black" style={{ color: score > 70 ? '#f43f5e' : score > 30 ? '#f59e0b' : '#10b981'}}>
            {score}<span className="text-base font-medium text-gray-400">/100</span>
          </div>
        </div>
      </div>

      {anomalies.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-2xl border border-gray-200 border-dashed">
          {/* This is what caused the crash! */}
          <CheckCircle2 className="w-12 h-12 text-emerald-400 mx-auto mb-3" />
          <h3 className="text-lg font-bold text-gray-900">No Anomalies Detected</h3>
          <p className="text-sm text-gray-500">This document conforms to standard patterns.</p>
        </div>
      ) : (
        <div className="space-y-4">
          <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">Detected Issues</h3>
          
          {anomalies.map((anom, idx) => {
            const config = getSeverityConfig(anom.severity);
            
            return (
              <div key={idx} className={`p-5 rounded-xl border shadow-sm flex items-start space-x-4 ${config.bg} ${config.border}`}>
                {config.icon}
                <div className="flex-1">
                  <div className="flex justify-between items-start mb-1">
                    <h4 className={`font-bold ${config.text} text-base`}>{anom.title}</h4>
                    <span className="text-[10px] font-bold uppercase tracking-wider bg-white/50 px-2 py-1 rounded border border-black/5">
                      {anom.category} Risk
                    </span>
                  </div>
                  <p className="text-sm text-gray-700 leading-relaxed mb-3">
                    {anom.explanation}
                  </p>
                  
                  {anom.evidence && (
                    <div className="bg-white/60 p-3 rounded-lg border border-black/5 text-sm font-medium text-gray-800">
                      <span className="text-xs font-bold text-gray-500 uppercase block mb-1">Extracted Evidence:</span>
                      "{anom.evidence}"
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}