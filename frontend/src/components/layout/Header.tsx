import React from 'react';
import { LayoutDashboard, Zap, Shield, Sparkles, Copy, Check } from 'lucide-react';
import { MarketIndexQuote } from '../../types/api';
import { formatCurrency, formatPercent } from '../../lib/utils';

interface HeaderProps {
  indices?: MarketIndexQuote[];
  activeView: string;
  onNavigateDashboard: () => void;
  clientId: string;
}

export const Header: React.FC<HeaderProps> = ({
  indices = [],
  activeView,
  onNavigateDashboard,
  clientId,
}) => {
  const [copied, setCopied] = React.useState(false);

  const copyClientId = () => {
    navigator.clipboard.writeText(clientId);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Fallback ticker items if indices are loading
  const defaultTickers = [
    { ticker: '^NSEI', name: 'NIFTY 50', price: 25420.50, change: 112.30, change_percent: 0.44, currency: 'INR' },
    { ticker: '^BSESN', name: 'SENSEX', price: 83190.20, change: 350.80, change_percent: 0.42, currency: 'INR' },
    { ticker: '^GSPC', name: 'S&P 500', price: 5715.40, change: -18.20, change_percent: -0.32, currency: 'USD' },
    { ticker: '^IXIC', name: 'NASDAQ 100', price: 17980.10, change: 85.40, change_percent: 0.48, currency: 'USD' },
    { ticker: 'TCS.NS', name: 'Tata Consultancy Services', price: 4120.50, change: 25.80, change_percent: 0.63, currency: 'INR' },
    { ticker: 'RELIANCE.NS', name: 'Reliance Ind', price: 2985.00, change: -15.40, change_percent: -0.51, currency: 'INR' },
    { ticker: 'NVDA', name: 'NVIDIA Corp', price: 124.60, change: 3.20, change_percent: 2.64, currency: 'USD' },
    { ticker: 'AAPL', name: 'Apple Inc', price: 228.30, change: 1.10, change_percent: 0.48, currency: 'USD' },
  ];

  const marqueeData = indices.length > 0 ? indices : defaultTickers;
  // Duplicate for seamless loop
  const tickerItems = [...marqueeData, ...marqueeData];

  return (
    <header className="sticky top-0 z-40 w-full bg-[#080C14]/95 backdrop-blur-md border-b border-slate-800/80">
      {/* 1. Market Marquee Ticker */}
      <div className="w-full bg-[#0A101D] border-b border-slate-800/60 overflow-hidden py-1.5 px-4 text-xs font-mono">
        <div className="flex items-center space-x-2">
          <div className="flex items-center space-x-1.5 shrink-0 pr-3 border-r border-slate-700/60 font-sans font-semibold text-sky-400">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-live"></span>
            <span className="tracking-wide uppercase text-[10px]">LIVE FEED</span>
          </div>

          <div className="overflow-hidden relative w-full">
            <div className="animate-marquee flex items-center space-x-8">
              {tickerItems.map((item, idx) => {
                const isPositive = item.change >= 0;
                return (
                  <div key={`${item.ticker}-${idx}`} className="flex items-center space-x-2 shrink-0">
                    <span className="font-semibold text-slate-200">{item.name || item.ticker}</span>
                    <span className="text-slate-400">{formatCurrency(item.price, item.currency)}</span>
                    <span
                      className={`inline-flex items-center text-[11px] font-medium px-1 rounded ${
                        isPositive
                          ? 'text-emerald-400 bg-emerald-950/40'
                          : 'text-rose-400 bg-rose-950/40'
                      }`}
                    >
                      {isPositive ? '▲' : '▼'} {formatPercent(item.change_percent)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* 2. Top Action Bar */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
        {/* Left: Market Dashboard button if in chat or other view */}
        <div className="flex items-center space-x-3">
          {activeView !== 'dashboard' ? (
            <button
              onClick={onNavigateDashboard}
              className="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-sky-500/10 hover:bg-sky-500/20 text-sky-400 border border-sky-500/30 transition shadow-sm font-medium text-sm group"
            >
              <LayoutDashboard className="w-4 h-4 text-sky-400 group-hover:scale-110 transition-transform" />
              <span>Market Dashboard</span>
            </button>
          ) : (
            <div className="flex items-center space-x-2 text-slate-400 text-xs font-mono">
              <span className="w-1.5 h-1.5 rounded-full bg-sky-400"></span>
              <span>TERMINAL OVERVIEW</span>
            </div>
          )}
        </div>

        {/* Right: Status Indicators & Anonymous UUID */}
        <div className="flex items-center space-x-3 text-xs">
          {/* Rate Limiter Status */}
          <div className="hidden sm:flex items-center space-x-1.5 px-2.5 py-1 rounded-md bg-slate-900 border border-slate-800 text-slate-300">
            <Shield className="w-3.5 h-3.5 text-emerald-400" />
            <span className="font-mono text-[11px]">25 req/min</span>
          </div>

          {/* Engine Badge */}
          <div className="hidden md:flex items-center space-x-1.5 px-2.5 py-1 rounded-md bg-slate-900 border border-slate-800 text-slate-300">
            <Sparkles className="w-3.5 h-3.5 text-amber-400" />
            <span>Gemini 2.0 Flash</span>
          </div>

          {/* Anonymous Client ID Pill */}
          <button
            onClick={copyClientId}
            title={`Your anonymous client UUID: ${clientId} (Click to copy)`}
            className="flex items-center space-x-1.5 px-2.5 py-1 rounded-md bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-400 hover:text-slate-200 transition font-mono text-[11px]"
          >
            <span>UUID:</span>
            <span className="text-sky-400">{clientId.slice(0, 8)}...</span>
            {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
          </button>
        </div>
      </div>
    </header>
  );
};
