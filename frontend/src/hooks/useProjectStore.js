import { useState, useCallback } from 'react';

// Mock initial data
const INITIAL_PROJECTS = [
  { id: 'p_1', name: 'Acme Corp Supplier Agreement', updatedAt: 'Just now', docCount: 0 },
  { id: 'p_2', name: 'Q3 Financial Audits', updatedAt: '2 hours ago', docCount: 3 }
];

export function useProjectStore() {
  const [projects, setProjects] = useState(INITIAL_PROJECTS);
  const [documents, setDocuments] = useState({});
  
  // Wrap the WebSocket connection in a Promise so we can await it
  const connectPipeline = useCallback((clientId, docId) => {
    return new Promise((resolve) => {
      const ws = new WebSocket(`ws://localhost:8000/ws/${clientId}`);
      
      // Resolve the promise ONLY when the connection is fully open
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

          // Mark document complete if the final risk stage completes
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

  const uploadDocument = async (projectId, file) => {
    const docId = Math.random().toString(36).substring(7);
    const clientId = docId;
    const fileUrl = URL.createObjectURL(file);

    // 1. Create document card immediately
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
        anomaly: { status: 'pending' }, // Added to initial state
        risk: { status: 'pending' }     // Added to initial state
      }
    };

    setDocuments(prev => ({ ...prev, [docId]: newDoc }));
    setProjects(prev => prev.map(p => p.id === projectId ? { ...p, docCount: p.docCount + 1 } : p));

    // 2. CRITICAL FIX: Await the WebSocket connection BEFORE uploading
    await connectPipeline(clientId, docId);

    // 3. Now trigger the backend upload knowing the WS is listening
    const formData = new FormData();
    formData.append('file', file);

    try {
      await fetch(`http://localhost:8000/api/upload?client_id=${clientId}`, {
        method: 'POST',
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