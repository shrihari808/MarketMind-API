import React, { useState } from 'react';
import {
  Search,
  TrendingUp,
  TrendingDown,
  Building,
  DollarSign,
  PieChart,
  Activity,
  FileText,
  Loader2,
  AlertCircle,
  Sparkles,
} from 'lucide-react';
import { ConsolidatedStockProfile } from '../../types/api';
import { api } from '../../lib/api';
import { formatCurrency, formatPercent, formatCompactNumber } from '../../lib/utils';

interface StockInspectorViewProps {
  initialTicker?: string;
  onAskAboutStock: (query: string) => void;
  clientId: string;
}

export const StockInspectorView: React.FC<StockInspectorViewProps> = ({
  initialTicker = 'TATAMOTORS.NS',
  onAskAboutStock,
  clientId,
}) => {
  const [ticker, setTicker] = useState(initialTicker);
  const [profile, setProfile] = useState<ConsolidatedStockProfile | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (targetTicker: string = ticker) => {
    if (!targetTicker.trim() || isLoading) return;
    setIsLoading(true);
    setError(null);

    try {
      const data = await api.getStockProfile(targetTicker.trim(), clientId);
      setProfile(data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch stock profile.');
    } finally {
      setIsLoading(false);
    }
  };

  const quote = profile?.quote;
  const funds = profile?.fundamentals;
  const isPositive = (quote?.change ?? 0) >= 0;

  return (
    <div className="space-y-6 pb-28 max-w-5xl mx-auto">
      {/* Header */}
      <div className="pb-4 border-b border-slate-800">
        <div className="flex items-center space-x-2.5">
          <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <Search className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">Stock Inspector & Valuation Multiples</h1>
            <p className="text-xs text-slate-400">
              Live quote and comprehensive financial fundamentals via YFinance for Indian (.NS) and US exchanges
            </p>
          </div>
        </div>
      </div>

      {/* Ticker Search Box */}
      <div className="p-4 rounded-xl bg-[#0E1626] border border-slate-800/80 shadow-md">
        <div className="flex items-center space-x-2">
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSearch(ticker);
            }}
            placeholder="Enter ticker (e.g. TATAMOTORS.NS, RELIANCE.NS, NVDA, AAPL)..."
            className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 font-mono uppercase focus:outline-none focus:border-sky-500"
          />
          <button
            onClick={() => handleSearch(ticker)}
            disabled={isLoading || !ticker.trim()}
            className="flex items-center space-x-1.5 px-4 py-2 rounded-lg bg-sky-500 hover:bg-sky-400 text-white font-semibold text-xs transition disabled:opacity-50 shadow-md shadow-sky-500/20"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Fetching...</span>
              </>
            ) : (
              <>
                <Search className="w-3.5 h-3.5" />
                <span>Inspect</span>
              </>
            )}
          </button>
        </div>

        {/* Shortcut chips */}
        <div className="flex items-center space-x-2 mt-3 text-xs overflow-x-auto">
          <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">Common:</span>
          {['TATAMOTORS.NS', 'RELIANCE.NS', 'HDFCBANK.NS', 'NVDA', 'AAPL', 'MSFT'].map((t) => (
            <button
              key={t}
              onClick={() => {
                setTicker(t);
                handleSearch(t);
              }}
              className="px-2 py-0.5 rounded bg-slate-800/70 hover:bg-slate-700 text-slate-300 font-mono text-[11px] transition"
            >
              {t}
            </button>
          ))}
        </div>

        {error && (
          <div className="mt-3 p-3 rounded-lg bg-rose-950/30 border border-rose-500/30 text-xs text-rose-300 flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* Stock Details */}
      {profile && (
        <div className="space-y-6">
          {/* Quote Overview Card */}
          <div className="p-6 rounded-xl bg-[#0E1626] border border-slate-800/80 shadow-lg">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
              <div>
                <div className="flex items-center space-x-3">
                  <span className="font-mono text-sm px-2.5 py-0.5 rounded bg-sky-500/10 text-sky-400 font-bold border border-sky-500/20">
                    {profile.ticker}
                  </span>
                  <h2 className="text-xl font-bold text-white tracking-tight">
                    {quote?.name || profile.ticker}
                  </h2>
                </div>
                <div className="flex items-center space-x-2 text-xs text-slate-400 mt-1">
                  <span>{funds?.sector || 'Equities'}</span>
                  <span>•</span>
                  <span>{funds?.industry || 'Financial Markets'}</span>
                </div>
              </div>

              <div className="text-right">
                <div className="text-2xl font-bold font-mono text-white tracking-tight">
                  {formatCurrency(quote?.price, quote?.currency || funds?.currency || 'INR')}
                </div>
                <div
                  className={`inline-flex items-center space-x-1 font-mono text-xs font-semibold ${
                    isPositive ? 'text-emerald-400' : 'text-rose-400'
                  }`}
                >
                  {isPositive ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
                  <span>{formatPercent(quote?.change_percent)}</span>
                  <span>({isPositive ? '+' : ''}{quote?.change?.toFixed(2)})</span>
                </div>
              </div>
            </div>

            {/* Quick Stats Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-4 text-xs font-mono">
              <div className="p-3 rounded-lg bg-slate-900/50 border border-slate-800">
                <span className="text-slate-500 text-[10px] block">DAY RANGE</span>
                <span className="text-slate-200 font-semibold">
                  {formatCurrency(quote?.day_low, quote?.currency)} - {formatCurrency(quote?.day_high, quote?.currency)}
                </span>
              </div>
              <div className="p-3 rounded-lg bg-slate-900/50 border border-slate-800">
                <span className="text-slate-500 text-[10px] block">VOLUME</span>
                <span className="text-slate-200 font-semibold">{formatCompactNumber(quote?.volume)}</span>
              </div>
              <div className="p-3 rounded-lg bg-slate-900/50 border border-slate-800">
                <span className="text-slate-500 text-[10px] block">MARKET CAP</span>
                <span className="text-slate-200 font-semibold">{formatCompactNumber(funds?.market_cap)}</span>
              </div>
              <div className="p-3 rounded-lg bg-slate-900/50 border border-slate-800">
                <span className="text-slate-500 text-[10px] block">CURRENCY</span>
                <span className="text-slate-200 font-semibold">{quote?.currency || funds?.currency || 'INR'}</span>
              </div>
            </div>
          </div>

          {/* Fundamentals & Valuation Ratios */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <MetricCard
              title="Price-to-Earnings (P/E)"
              value={funds?.pe_ratio ? `${funds.pe_ratio.toFixed(2)}x` : '—'}
              subtext="Trailing 12-month valuation multiple"
            />
            <MetricCard
              title="Price-to-Book (P/B)"
              value={funds?.pb_ratio ? `${funds.pb_ratio.toFixed(2)}x` : '—'}
              subtext="Valuation against net asset value"
            />
            <MetricCard
              title="Return on Equity (ROE)"
              value={funds?.roe ? `${(funds.roe * 100).toFixed(2)}%` : '—'}
              subtext="Capital profitability efficiency"
            />
            <MetricCard
              title="Debt-to-Equity Ratio"
              value={funds?.debt_to_equity ? `${funds.debt_to_equity.toFixed(2)}` : '—'}
              subtext="Balance sheet leverage posture"
            />
            <MetricCard
              title="Dividend Yield"
              value={funds?.dividend_yield ? `${(funds.dividend_yield * 100).toFixed(2)}%` : '—'}
              subtext="Annual cash return to shareholders"
            />
            <MetricCard
              title="Free Cash Flow"
              value={formatCompactNumber(funds?.free_cash_flow)}
              subtext="Operating cash minus capital expenditures"
            />
          </div>

          {/* Action Trigger: Ask AI */}
          <div className="p-4 rounded-xl bg-gradient-to-r from-sky-950/40 to-indigo-950/40 border border-sky-500/30 flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Sparkles className="w-5 h-5 text-sky-400" />
              <div>
                <h3 className="text-xs font-bold text-white">Ask AI Deep Dive on {profile.ticker}</h3>
                <p className="text-[11px] text-slate-400">
                  Trigger multi-angle Web RAG with live quotes and valuation thesis.
                </p>
              </div>
            </div>

            <button
              onClick={() => onAskAboutStock(`Give me a detailed valuation outlook and financial health analysis of ${profile.ticker}`)}
              className="px-4 py-2 rounded-lg bg-sky-500 hover:bg-sky-400 text-white font-semibold text-xs transition shadow-md shadow-sky-500/20"
            >
              Analyze with AI
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

const MetricCard: React.FC<{ title: string; value: string; subtext: string }> = ({
  title,
  value,
  subtext,
}) => (
  <div className="p-4 rounded-xl bg-[#0E1626] border border-slate-800/80">
    <div className="text-slate-400 text-xs font-medium mb-1">{title}</div>
    <div className="text-lg font-bold font-mono text-white mb-1">{value}</div>
    <div className="text-[10px] text-slate-500 leading-snug">{subtext}</div>
  </div>
);
