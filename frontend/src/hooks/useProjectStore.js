import { useState, useCallback } from 'react';

// Mock initial data
const INITIAL_PROJECTS = [
  { id: 'p_1', name: 'Acme Corp Supplier Agreement', updatedAt: 'Just now', docCount: 0 },
  { id: 'p_2', name: 'Q3 Financial Audits', updatedAt: '2 hours ago', docCount: 3 }
];

export function useProjectStore() {
  const [projects, setProjects] = useState(INITIAL_PROJECTS);
  const [documents, setDocuments] = useState({}); // { docId: DocumentObject }
  
  // Connects to your FastAPI websocket
  const connectPipeline = useCallback((clientId, docId) => {
    const ws = new WebSocket(`ws://localhost:8000/ws/${clientId}`);
    
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

        // If extraction is complete, mark the whole doc as complete
        const overallStatus = (payload.stage === 'extraction' && payload.status === 'complete') 
          ? 'completed' : doc.status;

        return {
          ...prev,
          [docId]: { ...doc, stages: newStages, status: overallStatus }
        };
      });
    };
  }, []);

  const uploadDocument = async (projectId, file) => {
    const docId = Math.random().toString(36).substring(7);
    const clientId = docId; // Use docId as clientId for WS
    
    // Create a local blob URL so we can render the PDF/Image immediately
    const fileUrl = URL.createObjectURL(file);

    // 1. Immediately create the document card in "Processing" state
    const newDoc = {
      id: docId,
      projectId,
      name: file.name,
      type: file.type,
      size: file.size,
      fileUrl,
      status: 'processing', // 'processing', 'completed', 'failed'
      stages: {
        ingestion: { status: 'pending' },
        classification: { status: 'pending' },
        extraction: { status: 'pending' }
      }
    };

    setDocuments(prev => ({ ...prev, [docId]: newDoc }));
    
    // Update project count
    setProjects(prev => prev.map(p => p.id === projectId ? { ...p, docCount: p.docCount + 1 } : p));

    // 2. Start WebSocket and trigger backend HTTP upload
    connectPipeline(clientId, docId);

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