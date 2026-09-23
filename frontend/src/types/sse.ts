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
  token?: string;
  text?: string;
}

export interface SSECompletePayload {
  total_tokens?: number;
  tokens_used?: number;
  latency?: number;
  duration_seconds?: number;
  session_id?: string;
}

export interface SSEErrorPayload {
  message?: string;
  error?: string;
  detail?: string;
}
