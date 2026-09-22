import { useState, useCallback, useRef } from 'react';
import { SourceCitation } from '../types/api';
import { SSEStatusPayload, SSESourcesPayload, SSETokenPayload, SSEErrorPayload } from '../types/sse';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export interface StreamState {
  isStreaming: boolean;
  statusStep: string;
  statusMessage: string;
  streamedText: string;
  sources: SourceCitation[];
  error: string | null;
}

export function useSSEStream(clientId: string) {
  const [streamState, setStreamState] = useState<StreamState>({
    isStreaming: false,
    statusStep: '',
    statusMessage: '',
    streamedText: '',
    sources: [],
    error: null,
  });

  const abortControllerRef = useRef<AbortController | null>(null);

  const stopStreaming = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setStreamState((prev) => ({ ...prev, isStreaming: false }));
  }, []);

  const startStream = useCallback(
    async ({
      endpoint,
      body,
      isFormData = false,
      onToken,
      onComplete,
    }: {
      endpoint: string;
      body: any;
      isFormData?: boolean;
      onToken?: (token: string, fullText: string) => void;
      onComplete?: (fullText: string, sources: SourceCitation[]) => void;
    }) => {
      // Abort any previous stream
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      const controller = new AbortController();
      abortControllerRef.current = controller;

      setStreamState({
        isStreaming: true,
        statusStep: 'init',
        statusMessage: 'Connecting to MarketMind AI engine...',
        streamedText: '',
        sources: [],
        error: null,
      });

      let accumulatedText = '';
      let accumulatedSources: SourceCitation[] = [];

      try {
        const headers: Record<string, string> = {
          'Accept': 'text/event-stream',
          'X-Client-ID': clientId,
        };

        let requestBody: any = body;
        if (!isFormData) {
          headers['Content-Type'] = 'application/json';
          requestBody = JSON.stringify(body);
        }

        const response = await fetch(`${API_BASE}${endpoint}`, {
          method: 'POST',
          headers,
          body: requestBody,
          signal: controller.signal,
        });

        if (response.status === 429) {
          const retry = response.headers.get('Retry-After') || '60';
          throw new Error(`Rate limit exceeded (25 req/min). Please try again in ${retry} seconds.`);
        }

        if (!response.ok) {
          let errText = `Server error ${response.status}: ${response.statusText}`;
          try {
            const errJson = await response.json();
            errText = errJson.detail || errJson.error || errText;
          } catch {
            // ignore
          }
          throw new Error(errText);
        }

        if (!response.body) {
          throw new Error('Response body is empty');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || ''; // Keep trailing incomplete line in buffer

          let currentEvent = 'message';

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed) {
              currentEvent = 'message';
              continue;
            }

            if (trimmed.startsWith('event:')) {
              currentEvent = trimmed.replace('event:', '').trim();
            } else if (trimmed.startsWith('data:')) {
              const rawData = trimmed.replace('data:', '').trim();
              if (!rawData) continue;

              try {
                const parsed = JSON.parse(rawData);

                switch (currentEvent) {
                  case 'status': {
                    const statusPayload = parsed as SSEStatusPayload;
                    setStreamState((prev) => ({
                      ...prev,
                      statusStep: statusPayload.step || 'processing',
                      statusMessage: statusPayload.message || 'Processing query...',
                    }));
                    break;
                  }

                  case 'sources': {
                    const sourcesPayload = parsed as SSESourcesPayload;
                    if (sourcesPayload.sources && Array.isArray(sourcesPayload.sources)) {
                      accumulatedSources = sourcesPayload.sources;
                      setStreamState((prev) => ({
                        ...prev,
                        sources: accumulatedSources,
                      }));
                    }
                    break;
                  }

                  case 'token': {
                    const tokenPayload = parsed as SSETokenPayload;
                    const tokenStr = tokenPayload.text || '';
                    accumulatedText += tokenStr;
                    setStreamState((prev) => ({
                      ...prev,
                      streamedText: accumulatedText,
                      statusMessage: '', // Clear status when tokens start arriving
                    }));
                    if (onToken) onToken(tokenStr, accumulatedText);
                    break;
                  }

                  case 'complete': {
                    // Stream completed normally
                    break;
                  }

                  case 'error': {
                    const errorPayload = parsed as SSEErrorPayload;
                    throw new Error(errorPayload.error || errorPayload.detail || 'Streaming error');
                  }
                }
              } catch (e: any) {
                // If it's a JSON parse error on non-json data, treat as raw token
                if (currentEvent === 'token' || currentEvent === 'message') {
                  accumulatedText += rawData;
                  setStreamState((prev) => ({ ...prev, streamedText: accumulatedText }));
                }
              }
            }
          }
        }

        setStreamState((prev) => ({
          ...prev,
          isStreaming: false,
          statusStep: 'complete',
          statusMessage: '',
        }));

        if (onComplete) {
          onComplete(accumulatedText, accumulatedSources);
        }
      } catch (err: any) {
        if (err.name === 'AbortError') {
          setStreamState((prev) => ({
            ...prev,
            isStreaming: false,
            statusMessage: 'Request paused by user.',
          }));
        } else {
          const message = err.message || 'An unexpected error occurred during streaming.';
          setStreamState((prev) => ({
            ...prev,
            isStreaming: false,
            error: message,
          }));
        }
      } finally {
        abortControllerRef.current = null;
      }
    },
    [clientId]
  );

  return {
    ...streamState,
    startStream,
    stopStreaming,
  };
}
