import React, { useEffect, useRef } from 'react';
import {
  Sparkles,
  User,
  Loader2,
  AlertTriangle,
} from 'lucide-react';
import { ChatMessageItem, SourceCitation, PromptSuggestion } from '../../types/api';
import { MarkdownRenderer } from '../common/MarkdownRenderer';
import { SourcesPopover } from './SourcesPopover';

interface FinancialChatViewProps {
  messages: ChatMessageItem[];
  isStreaming: boolean;
  streamingText: string;
  streamingStatus: string;
  streamingSources: SourceCitation[];
  streamingError: string | null;
  onSuggestionClick: (prompt: string) => void;
  suggestions?: PromptSuggestion[];
}

export const FinancialChatView: React.FC<FinancialChatViewProps> = ({
  messages,
  isStreaming,
  streamingText,
  streamingStatus,
  streamingSources,
  streamingError,
  onSuggestionClick,
  suggestions,
}) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingText, streamingStatus]);

  const defaultCards = [
    {
      title: 'Tata Motors EV Roadmap',
      desc: 'Analyze JLR electrification timeline and domestic passenger EV market share.',
    },
    {
      title: 'Reliance Industries Capex',
      desc: 'Assess 5G rollout returns, retail segment growth, and net debt position.',
    },
    {
      title: 'Nvidia Blackwell Demand',
      desc: 'Evaluate data center revenue catalysts and hyperscaler AI infrastructure capex.',
    },
    {
      title: 'S&P 500 Valuation Multiples',
      desc: 'Historical P/E comparison against long-term averages in declining rate regimes.',
    },
  ];

  const cards = (suggestions && suggestions.length > 0)
    ? suggestions.slice(0, 4).map(s => ({ title: s.header, desc: s.prompt }))
    : defaultCards;

  return (
    <div className="flex-1 flex flex-col h-full max-w-4xl mx-auto px-2 sm:px-4 w-full pb-36">
      {/* Empty State if no messages */}
      {messages.length === 0 && !isStreaming && !streamingError && (
        <div className="flex-1 flex flex-col items-center justify-center text-center p-6 sm:p-8">
          <div className="w-14 h-14 rounded-2xl bg-[#9013fe]/15 border border-[#9013fe]/30 flex items-center justify-center mb-4 text-[#d8b4fe] shadow-xl shadow-[#9013fe]/10">
            <Sparkles className="w-7 h-7" />
          </div>
          <h2 className="text-xl sm:text-2xl font-bold text-white mb-2 tracking-tight">
            MarketMind AI Financial Research
          </h2>
          <p className="text-xs sm:text-sm text-slate-400 max-w-md mb-8 leading-relaxed">
            Ask complex valuation, earnings, capex, or competitive moat questions. Backed by live
            web retrieval, real-time quotes, and institutional AI research.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-xl text-left">
            {cards.map((card, idx) => (
              <button
                key={idx}
                onClick={() => onSuggestionClick(card.desc)}
                className="p-3.5 rounded-xl bg-[#221f23] hover:bg-[#2d282f] border border-[#3d363f] hover:border-[#9013fe]/50 text-left transition group shadow-sm"
              >
                <div className="text-xs font-semibold text-slate-200 group-hover:text-[#d8b4fe] transition mb-1">
                  {card.title}
                </div>
                <div className="text-[11px] text-slate-400 line-clamp-2 leading-relaxed">{card.desc}</div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Message List */}
      <div className="space-y-8 pt-4">
        {messages.map((msg, index) => (
          <div key={index} className="space-y-4">
            {msg.role === 'user' ? (
              <div className="flex items-start space-x-3 justify-end">
                <div className="max-w-2xl rounded-2xl rounded-tr-sm bg-[#9013fe]/20 border border-[#9013fe]/40 text-slate-100 px-4 py-3 text-sm shadow-md font-sans">
                  {msg.content}
                </div>
                <div className="w-8 h-8 rounded-full bg-[#221f23] border border-[#3d363f] flex items-center justify-center text-slate-300 shrink-0">
                  <User className="w-4 h-4" />
                </div>
              </div>
            ) : (
              <div className="flex items-start space-x-3.5">
                <div className="w-8 h-8 rounded-full bg-[#9013fe]/20 border border-[#9013fe]/30 flex items-center justify-center text-[#d8b4fe] shrink-0 mt-1">
                  <Sparkles className="w-4 h-4" />
                </div>

                <div className="flex-1 min-w-0 space-y-2">
                  {/* Seamless Response Rendering (NO box background or border) */}
                  <div className="text-sm text-slate-200 leading-relaxed font-sans py-0.5">
                    <MarkdownRenderer content={msg.content} sources={msg.sources} />
                  </div>

                  {/* Expandable Sources Button with Preview of 3 Favicons */}
                  {msg.sources && msg.sources.length > 0 && (
                    <SourcesPopover sources={msg.sources} />
                  )}
                </div>
              </div>
            )}
          </div>
        ))}

        {/* Live Streaming Response Card */}
        {isStreaming && (
          <div className="flex items-start space-x-3.5">
            <div className="w-8 h-8 rounded-full bg-[#9013fe]/20 border border-[#9013fe]/30 flex items-center justify-center text-[#d8b4fe] shrink-0 mt-1">
              <Sparkles className="w-4 h-4 animate-spin" />
            </div>

            <div className="flex-1 min-w-0 space-y-2">
              {/* Progress Stepper Banner */}
              {streamingStatus && (
                <div className="inline-flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-[#9013fe]/10 border border-[#9013fe]/30 text-xs text-[#d8b4fe] animate-pulse font-mono mb-2">
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-[#c084fc] shrink-0" />
                  <span>{streamingStatus}</span>
                </div>
              )}

              {/* Streaming Content seamlessly onto background */}
              {streamingText ? (
                <div className="text-sm text-slate-200 leading-relaxed font-sans py-0.5">
                  <MarkdownRenderer content={streamingText} sources={streamingSources} isStreaming />
                </div>
              ) : (
                <div className="text-sm text-slate-400 animate-pulse font-sans py-1">
                  Synthesizing financial information...
                </div>
              )}

              {/* Expandable Sources Button during streaming */}
              {streamingSources.length > 0 && (
                <SourcesPopover sources={streamingSources} />
              )}
            </div>
          </div>
        )}

        {/* Streaming Error Banner */}
        {streamingError && (
          <div className="flex items-center space-x-3 p-4 rounded-xl bg-rose-950/30 border border-rose-500/40 text-xs text-rose-300 max-w-2xl mx-auto">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
            <div className="flex-1 font-sans">{streamingError}</div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
};
