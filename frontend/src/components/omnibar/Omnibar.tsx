import React, { useState, useRef, useEffect } from 'react';
import { Send, Square, Sparkles, ChevronDown, Check } from 'lucide-react';

interface OmnibarProps {
  country: 'IN' | 'US';
  onSelectCountry: (country: 'IN' | 'US') => void;
  onSubmitPrompt: (prompt: string) => void;
  onSelectSuggestion?: (prompt: string) => void;
  isStreaming?: boolean;
  onStopStreaming?: () => void;
  placeholder?: string;
}

export const Omnibar: React.FC<OmnibarProps> = ({
  country,
  onSelectCountry,
  onSubmitPrompt,
  onSelectSuggestion,
  isStreaming = false,
  onStopStreaming,
  placeholder = "Ask any financial question (e.g. 'Tata Motors EV outlook', 'Nvidia Blackwell GPU demand')...",
}) => {
  const [prompt, setPrompt] = useState('');
  const [isCountryDropdownOpen, setIsCountryDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Close country dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsCountryDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSend = () => {
    const trimmed = prompt.trim();
    if (!trimmed || isStreaming) return;
    onSubmitPrompt(trimmed);
    setPrompt('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    if (onSelectSuggestion) {
      onSelectSuggestion(suggestion);
    } else {
      onSubmitPrompt(suggestion);
    }
  };

  const suggestions = country === 'IN'
    ? [
        { label: 'Tata Motors EV Growth', query: 'What is Tata Motors valuation outlook and EV strategy?' },
        { label: 'Reliance Q3 Capex', query: 'Analyze Reliance Industries capex and debt levels' },
        { label: 'HDFC Bank Margins', query: 'What is the latest NIM margin trend for HDFC Bank?' },
        { label: 'RELIANCE.NS', query: 'What is the stock performance and financial health of RELIANCE.NS?' },
      ]
    : [
        { label: 'Nvidia Blackwell Demand', query: 'What is the demand outlook for Nvidia Blackwell AI chips?' },
        { label: 'Apple Services Moat', query: 'Analyze Apple Services revenue growth and ecosystem moat' },
        { label: 'S&P 500 Fed Cuts', query: 'How will Fed interest rate cuts impact the S&P 500 tech sector?' },
        { label: 'NVDA', query: 'What is the valuation outlook and key risk factors for NVDA?' },
      ];

  return (
    <div className="w-full bg-[#2a262b]/95 backdrop-blur-xl border-t border-[#3d363f] p-3 sm:p-4 transition-all">
      <div className="max-w-4xl mx-auto">
        {/* Suggestion Shortcuts */}
        <div className="flex items-center space-x-2 overflow-x-auto pb-2 scrollbar-none text-xs">
          <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider shrink-0 flex items-center space-x-1">
            <Sparkles className="w-3 h-3 text-[#c084fc] inline" />
            <span>Shortcuts:</span>
          </span>
          {suggestions.map((item, idx) => (
            <button
              key={idx}
              onClick={() => handleSuggestionClick(item.query)}
              className="shrink-0 px-2.5 py-1 rounded-full bg-[#1d1a1e] hover:bg-[#3d363f] border border-[#3d363f] hover:border-[#9013fe]/60 text-slate-300 hover:text-white transition text-xs font-medium"
            >
              {item.label}
            </button>
          ))}
        </div>

        {/* Input Bar with Country Selector */}
        <div className="relative flex items-center rounded-xl bg-[#221f23] border border-[#3d363f] focus-within:border-[#9013fe] focus-within:ring-2 focus-within:ring-[#9013fe]/20 shadow-lg transition-all p-1.5">
          {/* Country Dropdown */}
          <div className="relative shrink-0" ref={dropdownRef}>
            <button
              type="button"
              onClick={() => setIsCountryDropdownOpen(!isCountryDropdownOpen)}
              className="flex items-center space-x-1.5 px-2.5 sm:px-3 py-2 rounded-lg bg-[#1d1a1e] hover:bg-[#3d363f] border border-[#3d363f] text-sm font-semibold text-slate-200 transition"
              title="Select Market Region"
            >
              <span className="text-base leading-none">{country === 'IN' ? '🇮🇳' : '🇺🇸'}</span>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
            </button>

            {isCountryDropdownOpen && (
              <div className="absolute bottom-full mb-2 left-0 w-38 rounded-lg bg-[#1d1a1e] border border-[#3d363f] shadow-xl overflow-hidden z-50 py-1 text-xs">
                <button
                  onClick={() => {
                    onSelectCountry('IN');
                    setIsCountryDropdownOpen(false);
                  }}
                  className={`w-full flex items-center justify-between px-3 py-2 text-left hover:bg-[#221f23] transition ${
                    country === 'IN' ? 'text-[#d8b4fe] font-bold bg-[#221f23]/80' : 'text-slate-300'
                  }`}
                >
                  <span className="flex items-center space-x-2">
                    <span className="text-base">🇮🇳</span>
                    <span>India</span>
                  </span>
                  {country === 'IN' && <Check className="w-3.5 h-3.5 text-[#c084fc]" />}
                </button>

                <button
                  onClick={() => {
                    onSelectCountry('US');
                    setIsCountryDropdownOpen(false);
                  }}
                  className={`w-full flex items-center justify-between px-3 py-2 text-left hover:bg-[#221f23] transition ${
                    country === 'US' ? 'text-[#d8b4fe] font-bold bg-[#221f23]/80' : 'text-slate-300'
                  }`}
                >
                  <span className="flex items-center space-x-2">
                    <span className="text-base">🇺🇸</span>
                    <span>United States</span>
                  </span>
                  {country === 'US' && <Check className="w-3.5 h-3.5 text-[#c084fc]" />}
                </button>
              </div>
            )}
          </div>

          {/* Search Input */}
          <input
            ref={inputRef}
            type="text"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isStreaming}
            placeholder={placeholder}
            className="flex-1 bg-transparent px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none disabled:opacity-50 min-w-0"
          />

          {/* Action Button: Send or Stop */}
          {isStreaming ? (
            <button
              onClick={onStopStreaming}
              title="Stop streaming"
              className="p-2 rounded-lg bg-rose-600/20 hover:bg-rose-600/30 text-rose-400 border border-rose-500/40 transition shrink-0"
            >
              <Square className="w-4 h-4 fill-current" />
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!prompt.trim()}
              title="Send question"
              className="p-2 rounded-lg bg-[#9013fe] hover:bg-[#7c0fd8] text-white disabled:opacity-30 disabled:hover:bg-[#9013fe] transition shadow-md shadow-[#9013fe]/20 shrink-0"
            >
              <Send className="w-4 h-4" />
            </button>
          )}
        </div>

        <div className="flex items-center justify-between mt-1 px-1 text-[11px] text-slate-400 font-mono">
          <span>Press Enter ↵ to search</span>
          <span>MarketMind Intelligence • Live Web RAG</span>
        </div>
      </div>
    </div>
  );
};
