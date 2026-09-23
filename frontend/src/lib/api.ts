import {
  MarketDashboardResponse,
  PromptSuggestion,
  MarketIndexQuote,
  ConsolidatedStockProfile,
  StockQuote,
  FinancialFundamentals,
  ChatSessionSummary,
  ChatMessageItem,
  RedditSentimentReport,
  DeepResearchReport,
  HealthStatusResponse
} from '../types/api';

const RAW_API_BASE = import.meta.env.VITE_API_BASE_URL || '';
export const API_BASE = RAW_API_BASE.replace(/\/+$/, '');

export function buildApiUrl(endpoint: string): string {
  const cleanEndpoint = endpoint.replace(/^\/+/, '/');
  return `${API_BASE}${cleanEndpoint}`;
}

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

  const url = buildApiUrl(endpoint);
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
  getDashboard: async (country: string = 'IN', forceRefresh: boolean = false, clientId?: string): Promise<MarketDashboardResponse> => {
    const refreshParam = forceRefresh ? '&force_refresh=true' : '';
    const raw = await request<any>(`/api/v2/dashboard?country=${encodeURIComponent(country)}${refreshParam}`, {}, clientId);
    const snapshot = raw?.data || raw || {};
    const isIndia = (snapshot?.country || country).toUpperCase() === 'IN';
    const currency = isIndia ? 'INR' : 'USD';

    const indices: MarketIndexQuote[] = (snapshot?.indices || []).map((idx: any) => ({
      ticker: idx.symbol || idx.ticker || '',
      name: idx.name || idx.symbol || '',
      price: typeof idx.price === 'number' ? idx.price : parseFloat(idx.price) || 0,
      change: typeof idx.change === 'number' ? idx.change : parseFloat(idx.change) || 0,
      change_percent: typeof idx.change_percent === 'number' ? idx.change_percent : parseFloat(idx.change_percent) || 0,
      currency: idx.currency || currency,
    }));

    const mapMovers = (list: any[]): StockQuote[] =>
      (list || []).map((item: any) => ({
        ticker: item.ticker || item.symbol || '',
        name: item.name || item.company_name || item.ticker || '',
        price: typeof item.price === 'number' ? item.price : parseFloat(item.price) || 0,
        change: typeof item.change === 'number' ? item.change : parseFloat(item.change) || 0,
        change_percent: typeof item.change_percent === 'number' ? item.change_percent : parseFloat(item.change_percent) || 0,
        currency: item.currency || currency,
        volume: item.volume ?? null,
      }));

    const prompt_suggestions: PromptSuggestion[] = (snapshot?.prompt_suggestions || [])
      .map((p: any) => ({
        header: (p.header || p.label || p.title || '').trim(),
        prompt: (p.prompt || p.query || p.desc || '').trim(),
      }))
      .filter((p: PromptSuggestion) => p.header.length > 0 && p.prompt.length > 0);

    return {
      country: snapshot?.country || country,
      last_updated: snapshot?.updated_at || snapshot?.last_updated || new Date().toISOString(),
      indices,
      gainers: mapMovers(snapshot?.top_gainers || snapshot?.gainers || []),
      losers: mapMovers(snapshot?.top_losers || snapshot?.losers || []),
      market_summary: snapshot?.market_sentiment || snapshot?.market_summary || '',
      prompt_suggestions,
      is_cached: !raw?.stale,
    };
  },

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

  getSessionMessages: async (sessionId: string, clientId: string): Promise<ChatMessageItem[]> => {
    const res = await request<any>(`/api/v2/chat/sessions/${encodeURIComponent(sessionId)}`, {}, clientId);
    if (Array.isArray(res)) return res;
    if (res && Array.isArray(res.messages)) return res.messages;
    return [];
  },

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
      body: JSON.stringify({ company_name: ticker, ticker, country, section_by_section: sectionBySection }),
    }, clientId),

  downloadResearchPdf: async (ticker: string, country: string = 'IN', sectionBySection: boolean = false, clientId?: string) => {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'Accept': 'application/pdf',
    };
    if (clientId) headers['X-Client-ID'] = clientId;

    const response = await fetch(buildApiUrl('/api/v2/research/pdf'), {
      method: 'POST',
      headers,
      body: JSON.stringify({ company_name: ticker, ticker, country, section_by_section: sectionBySection }),
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
