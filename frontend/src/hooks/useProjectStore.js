import { useState, useCallback } from 'react';

const INITIAL_PROJECTS = [
  { id: 'p_1', name: 'Acme Corp Supplier Agreement', updatedAt: 'Just now', docCount: 0 },
  { id: 'p_2', name: 'Q3 Financial Audits', updatedAt: '2 hours ago', docCount: 3 }
];

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export function useProjectStore() {
  const [projects, setProjects] = useState(INITIAL_PROJECTS);
  const [documents, setDocuments] = useState({});
  
  const connectPipeline = useCallback((clientId, docId) => {
    return new Promise((resolve) => {
      const ws = new WebSocket(`ws://localhost:8000/ws/${clientId}`);
      
      ws.onopen = () => {
        resolve(ws);
      };
      
      ws.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        setDocuments(prev => {
          const doc = prev[docId];
          if (!doc) return prev;
          
          const newStages = { ...doc.stages };
          newStages[payload.stage] = {
            status: payload.status,
            detail: payload.detail || newStages[payload.stage]?.detail,
            data: payload.data || newStages[payload.stage]?.data,
            error: payload.error || null,
          };

          const overallStatus = (payload.stage === 'risk' && payload.status === 'complete') 
            ? 'completed' : doc.status;

          return {
            ...prev,
            [docId]: { ...doc, stages: newStages, status: overallStatus }
          };
        });
      };
    });
  }, []);

  // ADDED 'mode' PARAMETER (Defaults to 'local')
  const uploadDocument = async (projectId, file, mode = 'local') => {
    const docId = Math.random().toString(36).substring(7);
    const clientId = docId;
    const fileUrl = URL.createObjectURL(file);

    const newDoc = {
      id: docId,
      projectId,
      name: file.name,
      type: file.type,
      size: file.size,
      fileUrl,
      status: 'processing',
      stages: {
        ingestion: { status: 'pending' },
        classification: { status: 'pending' },
        extraction: { status: 'pending' },
        anomaly: { status: 'pending' },
        risk: { status: 'pending' }
      }
    };

    setDocuments(prev => ({ ...prev, [docId]: newDoc }));
    setProjects(prev => prev.map(p => p.id === projectId ? { ...p, docCount: p.docCount + 1 } : p));

    await connectPipeline(clientId, docId);

    const formData = new FormData();
    formData.append('file', file);

    try {
      await fetch(`${API_URL}/api/upload?client_id=${clientId}`, {
        method: 'POST',
        // ADDED HEADERS FOR PROCESSING MODE
        headers: {
          'X-Processing-Mode': mode
        },
        body: formData,
      });
    } catch (err) {
      console.error('Upload failed:', err);
      setDocuments(prev => ({ 
        ...prev, 
        [docId]: { ...prev[docId], status: 'failed', stages: { ...prev[docId].stages, ingestion: { status: 'error', error: 'Network failure' } } }
      }));
    }
  };

  return { projects, documents, uploadDocument };
}