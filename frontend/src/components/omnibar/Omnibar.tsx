import React, { useState, useRef, useEffect } from 'react';
import { Send, Square, Sparkles, ChevronDown, Check } from 'lucide-react';
import { CountryFlag } from '../common/CountryFlag';

import { PromptSuggestion } from '../../types/api';

interface OmnibarProps {
  country: 'IN' | 'US';
  onSelectCountry: (country: 'IN' | 'US') => void;
  onSubmitPrompt: (prompt: string) => void;
  onSelectSuggestion?: (prompt: string) => void;
  isStreaming?: boolean;
  onStopStreaming?: () => void;
  placeholder?: string;
  suggestions?: PromptSuggestion[];
}

export const Omnibar: React.FC<OmnibarProps> = ({
  country,
  onSelectCountry,
  onSubmitPrompt,
  onSelectSuggestion,
  isStreaming = false,
  onStopStreaming,
  placeholder = "Ask any financial question (e.g. 'Tata Motors EV outlook', 'Nvidia Blackwell GPU demand')...",
  suggestions,
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

  const defaultSuggestions: PromptSuggestion[] = country === 'IN'
    ? [
        { header: 'Tata Motors EV', prompt: 'What is Tata Motors valuation outlook and EV strategy?' },
        { header: 'Reliance Capex', prompt: 'Analyze Reliance Industries capex and debt levels' },
        { header: 'HDFC Bank Margins', prompt: 'What is the latest NIM margin trend for HDFC Bank?' },
        { header: 'Nifty IT Sector', prompt: 'Analyze the valuation multiples and earnings growth outlook for Indian IT majors' },
      ]
    : [
        { header: 'Nvidia Blackwell', prompt: 'What is the demand outlook for Nvidia Blackwell AI chips?' },
        { header: 'Apple Services', prompt: 'Analyze Apple Services revenue growth and ecosystem moat' },
        { header: 'S&P 500 Fed Cuts', prompt: 'How will Fed interest rate cuts impact the S&P 500 tech sector?' },
        { header: 'Cloud Capex ROI', prompt: 'Evaluate cloud capex trends and AI infrastructure returns for Microsoft, Google, and Amazon' },
      ];

  const activeSuggestions = (suggestions && suggestions.length > 0)
    ? suggestions.slice(0, 4)
    : defaultSuggestions;

  return (
    <div className="w-full bg-[#2a262b]/95 backdrop-blur-xl border-t border-[#3d363f] px-3 py-2 sm:px-4 sm:py-3 pb-[max(0.6rem,env(safe-area-inset-bottom))] sm:pb-3 transition-all">
      <div className="max-w-4xl mx-auto">
        {/* Suggestion Shortcuts */}
        <div className="flex items-center space-x-2 overflow-x-auto pb-1.5 scrollbar-none text-xs">
          <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider shrink-0 flex items-center space-x-1">
            <Sparkles className="w-3 h-3 text-[#c084fc] inline" />
            <span>Shortcuts:</span>
          </span>
          {activeSuggestions.map((item, idx) => (
            <button
              key={idx}
              onClick={() => handleSuggestionClick(item.prompt)}
              className="shrink-0 px-2.5 py-1 rounded-full bg-[#1d1a1e] hover:bg-[#3d363f] border border-[#3d363f] hover:border-[#9013fe]/60 text-slate-300 hover:text-white transition text-xs font-medium"
              title={item.prompt}
            >
              {item.header}
            </button>
          ))}
        </div>

        {/* Input Bar with Country Selector */}
        <div className="relative flex items-center rounded-xl bg-[#221f23] border border-[#9013fe] focus-within:ring-2 focus-within:ring-[#9013fe]/20 shadow-lg transition-all p-1.5">
          {/* Country Dropdown */}
          <div className="relative shrink-0" ref={dropdownRef}>
            <button
              type="button"
              onClick={() => setIsCountryDropdownOpen(!isCountryDropdownOpen)}
              className="flex items-center space-x-1.5 px-2.5 sm:px-3 py-2 rounded-lg bg-[#1d1a1e] hover:bg-[#3d363f] border border-[#3d363f] text-sm font-semibold text-slate-200 transition"
              title="Select Market Region"
            >
              <CountryFlag country={country} className="w-5 h-3.5 rounded-xs" />
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
                    <CountryFlag country="IN" className="w-5 h-3.5 rounded-xs" />
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
                    <CountryFlag country="US" className="w-5 h-3.5 rounded-xs" />
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
          <span className="hidden sm:inline">Press Enter ↵ to search</span>
          <span className="text-[10px] sm:text-[11px] text-slate-400 truncate">MarketMind Intelligence • Live Web RAG</span>
        </div>
      </div>
    </div>
  );
};
