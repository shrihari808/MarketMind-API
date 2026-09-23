import React from 'react';
import { Menu } from 'lucide-react';
import { MarketIndexQuote } from '../../types/api';
import { formatCurrency, formatPercent } from '../../lib/utils';

interface HeaderProps {
  indices?: MarketIndexQuote[];
  onToggleMobileSidebar?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  indices = [],
  onToggleMobileSidebar,
}) => {
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

  const validIndices = (indices || []).filter((idx) => (idx.price ?? 0) > 0);
  const marqueeData = validIndices.length > 0 ? validIndices : defaultTickers;
  const tickerItems = [...marqueeData, ...marqueeData];

  return (
    <header className="sticky top-0 z-40 w-full bg-[#1d1a1e] border-b border-[#3d363f]">
      {/* Market Marquee Ticker */}
      <div className="w-full overflow-hidden py-1.5 px-3 sm:px-4 text-xs font-mono">
        <div className="flex items-center space-x-2">
          {onToggleMobileSidebar && (
            <button
              onClick={onToggleMobileSidebar}
              className="lg:hidden p-1 mr-1 rounded bg-[#221f23] hover:bg-[#3d363f] border border-[#3d363f] text-slate-300 transition shrink-0"
              title="Toggle Navigation Menu"
            >
              <Menu className="w-3.5 h-3.5" />
            </button>
          )}

          <div className="flex items-center space-x-1.5 shrink-0 pr-3 border-r border-[#3d363f] font-sans font-semibold text-[#d8b4fe]">
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
    </header>
  );
};
