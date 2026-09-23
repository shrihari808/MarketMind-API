import { useState, useCallback, useRef } from 'react';
import { SourceCitation } from '../types/api';
import { SSEStatusPayload, SSESourcesPayload, SSETokenPayload, SSEErrorPayload } from '../types/sse';
import { buildApiUrl } from '../lib/api';

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

        const response = await fetch(buildApiUrl(endpoint), {
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
        let currentEvent = 'message';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || ''; // Keep trailing incomplete line in buffer

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

                // 1. Token chunk detection (by event or payload fields)
                if (currentEvent === 'token' || parsed.token !== undefined || parsed.text !== undefined) {
                  const tokenStr = parsed.token ?? parsed.text ?? (typeof parsed === 'string' ? parsed : '');
                  accumulatedText += tokenStr;
                  setStreamState((prev) => ({
                    ...prev,
                    streamedText: accumulatedText,
                    statusMessage: '', // Clear status when tokens start arriving
                  }));
                  if (onToken) onToken(tokenStr, accumulatedText);
                }
                // 2. Sources metadata detection
                else if (currentEvent === 'sources' || parsed.sources !== undefined) {
                  const sourcesList = parsed.sources || (Array.isArray(parsed) ? parsed : []);
                  if (Array.isArray(sourcesList)) {
                    accumulatedSources = sourcesList;
                    setStreamState((prev) => ({
                      ...prev,
                      sources: accumulatedSources,
                    }));
                  }
                }
                // 3. Status stepper detection
                else if (currentEvent === 'status' || parsed.step !== undefined) {
                  const statusPayload = parsed as SSEStatusPayload;
                  setStreamState((prev) => ({
                    ...prev,
                    statusStep: statusPayload.step || 'processing',
                    statusMessage: statusPayload.message || 'Processing query...',
                  }));
                }
                // 4. Complete event detection
                else if (currentEvent === 'complete' || parsed.tokens_used !== undefined) {
                  // Stream completed normally
                }
                // 5. Error event detection
                else if (currentEvent === 'error' || parsed.error !== undefined) {
                  const errorPayload = parsed as SSEErrorPayload;
                  throw new Error(errorPayload.message || errorPayload.error || errorPayload.detail || 'Streaming error');
                }
              } catch (e: any) {
                // If it's a re-thrown streaming error from above, bubble up
                if (e.message && (currentEvent === 'error' || e.message.includes('Streaming error') || e.message.includes('Generation error'))) {
                  throw e;
                }
                // If it's a JSON parse error on non-json plain text stream, treat as raw token
                if (currentEvent === 'token' || currentEvent === 'message') {
                  accumulatedText += rawData;
                  setStreamState((prev) => ({
                    ...prev,
                    streamedText: accumulatedText,
                    statusMessage: '',
                  }));
                  if (onToken) onToken(rawData, accumulatedText);
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
