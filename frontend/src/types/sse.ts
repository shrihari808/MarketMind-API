import { SourceCitation } from './api';

export type SSEEventType = 'status' | 'sources' | 'token' | 'complete' | 'error';

export interface SSEStatusPayload {
  step: string;
  message: string;
}

export interface SSESourcesPayload {
  sources: SourceCitation[];
}

export interface SSETokenPayload {
  text: string;
}

export interface SSECompletePayload {
  total_tokens?: number;
  latency?: number;
  session_id?: string;
}

export interface SSEErrorPayload {
  error: string;
  detail?: string;
}
