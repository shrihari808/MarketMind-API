import {
  MarketDashboardResponse,
  ConsolidatedStockProfile,
  StockQuote,
  FinancialFundamentals,
  ChatSessionSummary,
  ChatMessageItem,
  RedditSentimentReport,
  DeepResearchReport,
  HealthStatusResponse
} from '../types/api';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export class ApiError extends Error {
  status: number;
  data: any;

  constructor(message: string, status: number, data?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}, clientId?: string): Promise<T> {
  const headers: Record<string, string> = {
    'Accept': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };

  if (clientId) {
    headers['X-Client-ID'] = clientId;
  }

  const url = `${API_BASE}${endpoint}`;
  const response = await fetch(url, { ...options, headers });

  if (response.status === 429) {
    const retryAfter = response.headers.get('Retry-After') || '60';
    throw new ApiError(`Rate limit reached (25 req/min). Please wait ${retryAfter}s.`, 429);
  }

  if (!response.ok) {
    let errorDetail = response.statusText;
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errJson.error || JSON.stringify(errJson);
    } catch {
      // ignore
    }
    throw new ApiError(errorDetail || `Request failed with status ${response.status}`, response.status);
  }

  return response.json() as Promise<T>;
}

export const api = {
  // --- Market Dashboard ---
  getDashboard: (country: string = 'IN', clientId?: string) =>
    request<MarketDashboardResponse>(`/api/v2/dashboard?country=${encodeURIComponent(country)}`, {}, clientId),

  // --- Stocks & Fundamentals ---
  getStockProfile: (ticker: string, clientId?: string) =>
    request<ConsolidatedStockProfile>(`/api/v2/stocks/${encodeURIComponent(ticker)}`, {}, clientId),

  getStockQuote: (ticker: string, clientId?: string) =>
    request<StockQuote>(`/api/v2/stocks/${encodeURIComponent(ticker)}/quote`, {}, clientId),

  getStockFundamentals: (ticker: string, clientId?: string) =>
    request<FinancialFundamentals>(`/api/v2/stocks/${encodeURIComponent(ticker)}/fundamentals`, {}, clientId),

  // --- Chat History (Anonymous Client UUID) ---
  getSessions: (clientId: string) =>
    request<ChatSessionSummary[]>('/api/v2/chat/sessions', {}, clientId),

  getSessionMessages: (sessionId: string, clientId: string) =>
    request<ChatMessageItem[]>(`/api/v2/chat/sessions/${encodeURIComponent(sessionId)}`, {}, clientId),

  deleteSession: (sessionId: string, clientId: string) =>
    request<{ success: boolean; message: string }>(`/api/v2/chat/sessions/${encodeURIComponent(sessionId)}`, {
      method: 'DELETE',
    }, clientId),

  // --- Reddit Sentiment ---
  getRedditSentiment: (topic: string, clientId?: string) =>
    request<RedditSentimentReport>('/api/v2/rag/reddit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic }),
    }, clientId),

  // --- Deep Equity Research ---
  generateResearchReport: (ticker: string, country: string = 'IN', sectionBySection: boolean = false, clientId?: string) =>
    request<DeepResearchReport>('/api/v2/research', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ticker, country, section_by_section: sectionBySection }),
    }, clientId),

  downloadResearchPdf: async (ticker: string, country: string = 'IN', sectionBySection: boolean = false, clientId?: string) => {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'Accept': 'application/pdf',
    };
    if (clientId) headers['X-Client-ID'] = clientId;

    const response = await fetch(`${API_BASE}/api/v2/research/pdf`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ ticker, country, section_by_section: sectionBySection }),
    });

    if (!response.ok) {
      throw new Error(`Failed to generate PDF: ${response.statusText}`);
    }

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${ticker.replace(/[^a-zA-Z0-9]/g, '_')}_Research_Report.pdf`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  },

  // --- System Health & Rate Limiter Control ---
  getHealth: () =>
    request<HealthStatusResponse>('/api/v2/health'),

  getRateLimitStatus: () =>
    request<{
      enabled: boolean;
      limit_per_minute: number;
      tracked_ips_count: number;
      client_ip?: string;
      remaining_requests?: number;
    }>('/api/v2/health/rate-limit'),
};
