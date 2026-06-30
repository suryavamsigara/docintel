import { useState, useEffect, useCallback } from 'react';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

export function usePipelineStream() {
  const [clientId, setClientId] = useState('');
  const [socket, setSocket] = useState(null);
  const [pipelineState, setPipelineState] = useState({
    ingestion: { status: 'pending', data: null, error: null, detail: '' },
    classification: { status: 'pending', data: null, error: null, detail: '' },
    extraction: { status: 'pending', data: null, error: null, detail: '' },
  });

  const connect = useCallback((newClientId) => {
    setClientId(newClientId);
    const ws = new WebSocket(`${WS_URL}/ws/${newClientId}`);
    
    ws.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      setPipelineState((prev) => ({
        ...prev,
        [payload.stage]: {
          status: payload.status,
          data: payload.data || prev[payload.stage].data,
          error: payload.error || null,
          detail: payload.detail || '',
        }
      }));
    };
    setSocket(ws);
  }, []);

  const resetPipeline = useCallback(() => {
    setPipelineState({
      ingestion: { status: 'pending', data: null, error: null, detail: '' },
      classification: { status: 'pending', data: null, error: null, detail: '' },
      extraction: { status: 'pending', data: null, error: null, detail: '' },
    });
  }, []);

  useEffect(() => { return () => { if (socket) socket.close(); }; }, [socket]);

  return { clientId, pipelineState, connect, resetPipeline };
}