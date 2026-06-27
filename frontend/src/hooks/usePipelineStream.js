import { useState, useEffect, useCallback } from 'react';

export function usePipelineStream() {
  const [clientId, setClientId] = useState('');
  const [socket, setSocket] = useState(null);
  const [pipelineState, setPipelineState] = useState({
    ingestion: { status: 'pending', data: null, error: null },
    classification: { status: 'pending', data: null, error: null },
    extraction: { status: 'pending', data: null, error: null },
    anomaly: { status: 'pending', data: null, error: null },
    risk: { status: 'pending', data: null, error: null },
  });

  const connect = useCallback((newClientId) => {
    setClientId(newClientId);
    const ws = new WebSocket(`ws://localhost:8000/ws/${newClientId}`);
    
    ws.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      setPipelineState((prev) => ({
        ...prev,
        [payload.stage]: {
          status: payload.status, // 'running', 'complete', 'error'
          data: payload.data || prev[payload.stage].data,
          error: payload.error || null,
        }
      }));
    };

    setSocket(ws);
  }, []);

  const resetPipeline = useCallback(() => {
    setPipelineState({
      ingestion: { status: 'pending', data: null, error: null },
      classification: { status: 'pending', data: null, error: null },
      extraction: { status: 'pending', data: null, error: null },
      anomaly: { status: 'pending', data: null, error: null },
      risk: { status: 'pending', data: null, error: null },
    });
  }, []);

  useEffect(() => {
    return () => {
      if (socket) socket.close();
    };
  }, [socket]);

  return { clientId, pipelineState, connect, resetPipeline };
}