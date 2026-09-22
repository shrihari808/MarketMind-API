import React from 'react';
import {
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Sparkles,
  BarChart2,
  Globe2,
  Clock,
  ArrowUpRight,
  ArrowDownRight,
} from 'lucide-react';
import { MarketDashboardResponse, StockQuote } from '../../types/api';
import { formatCurrency, formatPercent, formatCompactNumber } from '../../lib/utils';

interface MarketDashboardViewProps {
  country: 'IN' | 'US';
  dashboardData: MarketDashboardResponse | null;
  isLoading: boolean;
  onRefresh: () => void;
  onSelectTicker: (ticker: string) => void;
}

export const MarketDashboardView: React.FC<MarketDashboardViewProps> = ({
  country,
  dashboardData,
  isLoading,
  onRefresh,
  onSelectTicker,
}) => {
  return (
    <div className="space-y-6 pb-28">
      {/* 1. Header with Country Flag & Status */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800/80">
        <div>
          <div className="flex items-center space-x-3">
            <span className="text-2xl">{country === 'IN' ? '🇮🇳' : '🇺🇸'}</span>
            <h1 className="text-2xl font-bold tracking-tight text-white">
              {country === 'IN' ? 'Indian Markets Dashboard' : 'US Markets Dashboard'}
            </h1>
            <span className="px-2 py-0.5 rounded text-[11px] font-mono font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              SWR Active
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1 flex items-center space-x-2">
            <Globe2 className="w-3.5 h-3.5 text-slate-500" />
            <span>
              Real-time quotes via YFinance • Grounded AI Brief by Google Gemini 2.0 Flash
            </span>
          </p>
        </div>

        <div className="flex items-center space-x-3">
          {dashboardData?.last_updated && (
            <div className="flex items-center space-x-1.5 text-xs text-slate-400 font-mono">
              <Clock className="w-3.5 h-3.5 text-slate-500" />
              <span>
                Updated: {new Date(dashboardData.last_updated).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
          )}

          <button
            onClick={onRefresh}
            disabled={isLoading}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-medium transition disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-sky-400' : ''}`} />
            <span>{isLoading ? 'Refreshing...' : 'Refresh'}</span>
          </button>
        </div>
      </div>

      {/* 2. Benchmark Indices Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {isLoading && !dashboardData
          ? [1, 2, 3, 4].map((i) => (
              <div key={i} className="h-28 rounded-xl bg-slate-900/50 border border-slate-800 animate-pulse p-4" />
            ))
          : dashboardData?.indices.map((idx) => {
              const isPositive = idx.change >= 0;
              return (
                <div
                  key={idx.ticker}
                  className="rounded-xl bg-[#0E1626] border border-slate-800/80 p-4 hover:border-slate-700 transition shadow-sm"
                >
                  <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
                    <span className="font-semibold text-slate-300">{idx.name}</span>
                    <span className="font-mono text-[10px] text-slate-500">{idx.ticker}</span>
                  </div>

                  <div className="text-xl font-bold font-mono text-white tracking-tight my-1">
                    {formatCurrency(idx.price, idx.currency)}
                  </div>

                  <div className="flex items-center justify-between text-xs pt-1">
                    <span
                      className={`inline-flex items-center space-x-0.5 font-semibold font-mono ${
                        isPositive ? 'text-emerald-400' : 'text-rose-400'
                      }`}
                    >
                      {isPositive ? <ArrowUpRight className="w-3.5 h-3.5" /> : <ArrowDownRight className="w-3.5 h-3.5" />}
                      <span>{formatPercent(idx.change_percent)}</span>
                    </span>
                    <span className="text-[11px] font-mono text-slate-500">
                      {isPositive ? '+' : ''}{idx.change.toFixed(2)}
                    </span>
                  </div>
                </div>
              );
            })}
      </div>

      {/* 3. AI Macro Brief Card */}
      <div className="rounded-xl bg-gradient-to-br from-[#0E1626] to-[#0A101C] border border-sky-500/20 p-5 shadow-lg relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-sky-500/5 rounded-full blur-3xl pointer-events-none" />

        <div className="flex items-center space-x-2 text-sky-400 font-semibold text-sm mb-3">
          <Sparkles className="w-4 h-4 text-sky-400" />
          <span>Gemini Intelligence • Daily Market Macro Brief</span>
        </div>

        {isLoading && !dashboardData ? (
          <div className="space-y-2 animate-pulse">
            <div className="h-4 bg-slate-800 rounded w-3/4" />
            <div className="h-4 bg-slate-800 rounded w-full" />
            <div className="h-4 bg-slate-800 rounded w-5/6" />
          </div>
        ) : (
          <p className="text-sm text-slate-300 leading-relaxed font-sans">
            {dashboardData?.market_summary ||
              "Market participants are monitoring macroeconomic indicators, bond yields, and central bank commentary. Key sectors display mixed performance amid institutional portfolio rebalancing."}
          </p>
        )}
      </div>

      {/* 4. Top Gainers & Losers Tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Gainers */}
        <div className="rounded-xl bg-[#0E1626] border border-slate-800/80 p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-2 text-emerald-400 font-semibold text-sm">
              <TrendingUp className="w-4 h-4" />
              <span>Standout Gainers</span>
            </div>
            <span className="text-[11px] font-mono text-slate-500">Top Movers</span>
          </div>

          <div className="space-y-2.5">
            {dashboardData?.gainers && dashboardData.gainers.length > 0 ? (
              dashboardData.gainers.slice(0, 5).map((stock) => (
                <StockMoverRow
                  key={stock.ticker}
                  stock={stock}
                  isGain={true}
                  onSelectTicker={onSelectTicker}
                />
              ))
            ) : (
              <p className="text-xs text-slate-500 py-4 text-center">No gainers recorded</p>
            )}
          </div>
        </div>

        {/* Top Losers */}
        <div className="rounded-xl bg-[#0E1626] border border-slate-800/80 p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-2 text-rose-400 font-semibold text-sm">
              <TrendingDown className="w-4 h-4" />
              <span>Standout Decliners</span>
            </div>
            <span className="text-[11px] font-mono text-slate-500">Top Movers</span>
          </div>

          <div className="space-y-2.5">
            {dashboardData?.losers && dashboardData.losers.length > 0 ? (
              dashboardData.losers.slice(0, 5).map((stock) => (
                <StockMoverRow
                  key={stock.ticker}
                  stock={stock}
                  isGain={false}
                  onSelectTicker={onSelectTicker}
                />
              ))
            ) : (
              <p className="text-xs text-slate-500 py-4 text-center">No decliners recorded</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

interface StockMoverRowProps {
  stock: StockQuote;
  isGain: boolean;
  onSelectTicker: (ticker: string) => void;
}

const StockMoverRow: React.FC<StockMoverRowProps> = ({ stock, isGain, onSelectTicker }) => {
  return (
    <div
      onClick={() => onSelectTicker(stock.ticker)}
      className="flex items-center justify-between p-2.5 rounded-lg bg-slate-900/60 hover:bg-slate-800 border border-slate-800/60 hover:border-slate-700 cursor-pointer transition group"
    >
      <div>
        <div className="flex items-center space-x-2">
          <span className="font-bold text-xs text-slate-200 group-hover:text-sky-400 transition font-mono">
            {stock.ticker}
          </span>
          <span className="text-[11px] text-slate-400 truncate max-w-[140px] sm:max-w-[200px]">
            {stock.name}
          </span>
        </div>
        {stock.volume && (
          <span className="text-[10px] font-mono text-slate-500">
            Vol: {formatCompactNumber(stock.volume)}
          </span>
        )}
      </div>

      <div className="text-right">
        <div className="font-mono text-xs font-semibold text-slate-200">
          {formatCurrency(stock.price, stock.currency)}
        </div>
        <div
          className={`inline-flex items-center space-x-0.5 text-[11px] font-mono font-medium ${
            isGain ? 'text-emerald-400' : 'text-rose-400'
          }`}
        >
          <span>{formatPercent(stock.change_percent)}</span>
        </div>
      </div>
    </div>
  );
};
