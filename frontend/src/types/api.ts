export interface SourceCitation {
  id: number;
  url: string;
  title: string;
  snippet: string;
  publisher: string;
  published_date?: string | null;
}

export interface MarketIndexQuote {
  ticker: string;
  name: string;
  price: number;
  change: number;
  change_percent: number;
  currency: string;
}

export interface StockQuote {
  ticker: string;
  name: string;
  price: number;
  change: number;
  change_percent: number;
  currency: string;
  volume?: number | null;
  day_high?: number | null;
  day_low?: number | null;
}

export interface FinancialFundamentals {
  pe_ratio?: number | null;
  pb_ratio?: number | null;
  market_cap?: number | null;
  roe?: number | null;
  debt_to_equity?: number | null;
  dividend_yield?: number | null;
  revenue_growth?: number | null;
  free_cash_flow?: number | null;
  ebitda?: number | null;
  currency?: string | null;
  sector?: string | null;
  industry?: string | null;
  description?: string | null;
}

export interface ConsolidatedStockProfile {
  ticker: string;
  quote?: StockQuote | null;
  fundamentals?: FinancialFundamentals | null;
}

export interface MarketDashboardResponse {
  country: string;
  last_updated: string;
  indices: MarketIndexQuote[];
  gainers: StockQuote[];
  losers: StockQuote[];
  market_summary: string;
  is_cached?: boolean;
}

export interface ChatSessionSummary {
  session_id: string;
  title: string;
  message_count: number;
  created_at: string;
  last_activity: string;
}

export interface ChatMessageItem {
  id?: number;
  role: 'user' | 'assistant';
  content: string;
  created_at?: string;
  sources?: SourceCitation[];
  detected_ticker?: string | null;
  live_quote?: StockQuote | null;
}

export interface RedditSentimentReport {
  topic: string;
  sentiment: 'Bullish' | 'Bearish' | 'Neutral' | string;
  sentiment_score: number;
  bullish_arguments: string[];
  bearish_arguments: string[];
  summary: string;
  threads_analyzed: number;
  thread_links: string[];
}

export interface DeepResearchReport {
  ticker: string;
  company_name: string;
  country: string;
  generated_at: string;
  report_markdown: string;
  sections?: Record<string, string>;
}

export interface HealthStatusResponse {
  status: string;
  version: string;
  environment: string;
  database: string;
  search_provider: string;
  rate_limiting: {
    enabled: boolean;
    limit_per_minute: number;
  };
}
