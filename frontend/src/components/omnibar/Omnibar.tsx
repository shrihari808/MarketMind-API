import React, { useState, useRef, useEffect } from 'react';
import { Send, Square, Sparkles, ChevronDown, Check } from 'lucide-react';

interface OmnibarProps {
  country: 'IN' | 'US';
  onSelectCountry: (country: 'IN' | 'US') => void;
  onSubmitPrompt: (prompt: string) => void;
  isStreaming?: boolean;
  onStopStreaming?: () => void;
  placeholder?: string;
}

export const Omnibar: React.FC<OmnibarProps> = ({
  country,
  onSelectCountry,
  onSubmitPrompt,
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
    onSubmitPrompt(suggestion);
  };

  const suggestions = country === 'IN'
    ? [
        { label: 'Tata Motors EV Growth', query: 'What is Tata Motors valuation outlook and EV strategy?' },
        { label: 'Reliance Q3 Capex', query: 'Analyze Reliance Industries capex and debt levels' },
        { label: 'HDFC Bank Margins', query: 'What is the latest NIM margin trend for HDFC Bank?' },
        { label: 'TATAMOTORS.NS', query: 'What is the stock performance and financial health of TATAMOTORS.NS?' },
      ]
    : [
        { label: 'Nvidia Blackwell Demand', query: 'What is the demand outlook for Nvidia Blackwell AI chips?' },
        { label: 'Apple Services Moat', query: 'Analyze Apple Services revenue growth and ecosystem moat' },
        { label: 'S&P 500 Fed Cuts', query: 'How will Fed interest rate cuts impact the S&P 500 tech sector?' },
        { label: 'NVDA', query: 'What is the valuation outlook and key risk factors for NVDA?' },
      ];

  return (
    <div className="w-full bg-[#080C14]/90 backdrop-blur-xl border-t border-slate-800/80 p-4 transition-all">
      <div className="max-w-4xl mx-auto">
        {/* Suggestion Shortcuts */}
        <div className="flex items-center space-x-2 overflow-x-auto pb-2 scrollbar-none text-xs">
          <span className="text-[11px] font-mono text-slate-500 uppercase tracking-wider shrink-0 flex items-center space-x-1">
            <Sparkles className="w-3 h-3 text-sky-400 inline" />
            <span>Shortcuts:</span>
          </span>
          {suggestions.map((item, idx) => (
            <button
              key={idx}
              onClick={() => handleSuggestionClick(item.query)}
              className="shrink-0 px-2.5 py-1 rounded-full bg-slate-900/80 hover:bg-slate-800 border border-slate-700/60 hover:border-sky-500/50 text-slate-300 hover:text-white transition text-xs font-medium"
            >
              {item.label}
            </button>
          ))}
        </div>

        {/* Input Bar with Country Selector */}
        <div className="relative flex items-center rounded-xl bg-[#0E1626] border border-slate-700/80 focus-within:border-sky-500 focus-within:ring-2 focus-within:ring-sky-500/20 shadow-lg transition-all p-1.5">
          {/* Country Dropdown */}
          <div className="relative shrink-0" ref={dropdownRef}>
            <button
              type="button"
              onClick={() => setIsCountryDropdownOpen(!isCountryDropdownOpen)}
              className="flex items-center space-x-1.5 px-3 py-2 rounded-lg bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700 text-xs font-semibold text-slate-200 transition"
              title="Select Market Region"
            >
              <span>{country === 'IN' ? '🇮🇳 IN' : '🇺🇸 US'}</span>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
            </button>

            {isCountryDropdownOpen && (
              <div className="absolute bottom-full mb-2 left-0 w-36 rounded-lg bg-[#0F172A] border border-slate-700 shadow-xl overflow-hidden z-50 py-1 text-xs">
                <button
                  onClick={() => {
                    onSelectCountry('IN');
                    setIsCountryDropdownOpen(false);
                  }}
                  className={`w-full flex items-center justify-between px-3 py-2 text-left hover:bg-slate-800 transition ${
                    country === 'IN' ? 'text-sky-400 font-bold bg-slate-800/50' : 'text-slate-300'
                  }`}
                >
                  <span className="flex items-center space-x-2">
                    <span>🇮🇳</span>
                    <span>India (IN)</span>
                  </span>
                  {country === 'IN' && <Check className="w-3.5 h-3.5 text-sky-400" />}
                </button>

                <button
                  onClick={() => {
                    onSelectCountry('US');
                    setIsCountryDropdownOpen(false);
                  }}
                  className={`w-full flex items-center justify-between px-3 py-2 text-left hover:bg-slate-800 transition ${
                    country === 'US' ? 'text-sky-400 font-bold bg-slate-800/50' : 'text-slate-300'
                  }`}
                >
                  <span className="flex items-center space-x-2">
                    <span>🇺🇸</span>
                    <span>United States (US)</span>
                  </span>
                  {country === 'US' && <Check className="w-3.5 h-3.5 text-sky-400" />}
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
            className="flex-1 bg-transparent px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none disabled:opacity-50"
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
              className="p-2 rounded-lg bg-sky-500 hover:bg-sky-400 text-white disabled:opacity-30 disabled:hover:bg-sky-500 transition shadow-md shadow-sky-500/20 shrink-0"
            >
              <Send className="w-4 h-4" />
            </button>
          )}
        </div>

        <div className="flex items-center justify-between mt-1 px-1 text-[11px] text-slate-500 font-mono">
          <span>Press Enter ↵ to search</span>
          <span>Google Gemini 2.0 Flash • DuckDuckGo Web RAG</span>
        </div>
      </div>
    </div>
  );
};
