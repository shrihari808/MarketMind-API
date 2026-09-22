import React, { useEffect, useRef } from 'react';
import {
  Sparkles,
  User,
  ExternalLink,
  CheckCircle2,
  Loader2,
  TrendingUp,
  AlertTriangle,
  BookOpen,
} from 'lucide-react';
import { ChatMessageItem, SourceCitation } from '../../types/api';
import { getDomain } from '../../lib/utils';

interface FinancialChatViewProps {
  messages: ChatMessageItem[];
  isStreaming: boolean;
  streamingText: string;
  streamingStatus: string;
  streamingSources: SourceCitation[];
  streamingError: string | null;
  onSuggestionClick: (prompt: string) => void;
}

export const FinancialChatView: React.FC<FinancialChatViewProps> = ({
  messages,
  isStreaming,
  streamingText,
  streamingStatus,
  streamingSources,
  streamingError,
  onSuggestionClick,
}) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingText, streamingStatus]);

  return (
    <div className="flex-1 flex flex-col h-full max-w-4xl mx-auto px-4 w-full pb-36">
      {/* Empty State if no messages */}
      {messages.length === 0 && !isStreaming && !streamingError && (
        <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-sky-500/20 to-indigo-500/20 border border-sky-500/30 flex items-center justify-center mb-4 text-sky-400 shadow-xl shadow-sky-500/10">
            <Sparkles className="w-7 h-7" />
          </div>
          <h2 className="text-xl font-bold text-white mb-2 tracking-tight">
            MarketMind AI Financial Research
          </h2>
          <p className="text-sm text-slate-400 max-w-md mb-8">
            Ask complex valuation, earnings, capex, or competitive moat questions. Backed by live
            web retrieval, real-time quotes, and Google Gemini 2.0 Flash.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-xl text-left">
            {[
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
            ].map((card, idx) => (
              <button
                key={idx}
                onClick={() => onSuggestionClick(card.desc)}
                className="p-3.5 rounded-xl bg-[#0E1626] hover:bg-slate-800/80 border border-slate-800 hover:border-sky-500/40 text-left transition group shadow-sm"
              >
                <div className="text-xs font-semibold text-slate-200 group-hover:text-sky-400 transition mb-1">
                  {card.title}
                </div>
                <div className="text-[11px] text-slate-400 line-clamp-2">{card.desc}</div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Message List */}
      <div className="space-y-6 pt-4">
        {messages.map((msg, index) => (
          <div key={index} className="space-y-3">
            {msg.role === 'user' ? (
              <div className="flex items-start space-x-3 justify-end">
                <div className="max-w-2xl rounded-2xl rounded-tr-sm bg-gradient-to-r from-sky-600 to-blue-700 text-white px-4 py-3 text-sm shadow-md font-sans">
                  {msg.content}
                </div>
                <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300 shrink-0">
                  <User className="w-4 h-4" />
                </div>
              </div>
            ) : (
              <div className="flex items-start space-x-3">
                <div className="w-8 h-8 rounded-full bg-sky-500/20 border border-sky-500/30 flex items-center justify-center text-sky-400 shrink-0">
                  <Sparkles className="w-4 h-4" />
                </div>

                <div className="flex-1 space-y-3 max-w-3xl">
                  {/* Assistant Message Bubble */}
                  <div className="rounded-2xl rounded-tl-sm bg-[#0E1626] border border-slate-800 p-5 text-sm text-slate-200 leading-relaxed shadow-sm font-sans whitespace-pre-wrap">
                    {msg.content}
                  </div>

                  {/* Sources Citations */}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="rounded-xl bg-[#0A101D] border border-slate-800/70 p-3">
                      <div className="flex items-center space-x-1.5 text-xs font-semibold text-slate-400 mb-2">
                        <BookOpen className="w-3.5 h-3.5 text-sky-400" />
                        <span>Sources & Citations ({msg.sources.length})</span>
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {msg.sources.map((src) => (
                          <a
                            key={src.id}
                            href={src.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-start space-x-2 p-2 rounded-lg bg-slate-900/60 hover:bg-slate-850 border border-slate-800 hover:border-slate-700 transition group text-xs"
                          >
                            <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-400 font-bold shrink-0">
                              [{src.id}]
                            </span>
                            <div className="min-w-0 flex-1">
                              <p className="font-medium text-slate-300 truncate group-hover:text-sky-400 transition">
                                {src.title}
                              </p>
                              <div className="flex items-center space-x-1 text-[10px] text-slate-500 mt-0.5">
                                <span>{getDomain(src.url)}</span>
                                <ExternalLink className="w-2.5 h-2.5 opacity-50" />
                              </div>
                            </div>
                          </a>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        ))}

        {/* Live Streaming Response Card */}
        {isStreaming && (
          <div className="flex items-start space-x-3">
            <div className="w-8 h-8 rounded-full bg-sky-500/20 border border-sky-500/30 flex items-center justify-center text-sky-400 shrink-0">
              <Sparkles className="w-4 h-4 animate-spin" />
            </div>

            <div className="flex-1 space-y-3 max-w-3xl">
              {/* Progress Stepper Banner */}
              {streamingStatus && (
                <div className="flex items-center space-x-2.5 px-3.5 py-2 rounded-lg bg-sky-950/40 border border-sky-500/30 text-xs text-sky-300 animate-pulse font-mono">
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-sky-400 shrink-0" />
                  <span>{streamingStatus}</span>
                </div>
              )}

              {/* Streaming Content */}
              {streamingText ? (
                <div className="rounded-2xl rounded-tl-sm bg-[#0E1626] border border-slate-800 p-5 text-sm text-slate-200 leading-relaxed shadow-sm font-sans whitespace-pre-wrap">
                  {streamingText}
                  <span className="inline-block w-2 h-4 ml-1 bg-sky-400 animate-pulse align-middle" />
                </div>
              ) : (
                <div className="rounded-2xl rounded-tl-sm bg-[#0E1626] border border-slate-800 p-5 text-sm text-slate-400 animate-pulse">
                  Synthesizing financial intelligence via Gemini 2.0 Flash...
                </div>
              )}

              {/* Real-time Incoming Sources */}
              {streamingSources.length > 0 && (
                <div className="rounded-xl bg-[#0A101D] border border-slate-800/70 p-3">
                  <div className="flex items-center space-x-1.5 text-xs font-semibold text-slate-400 mb-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Scraped & Reranked Sources ({streamingSources.length})</span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {streamingSources.map((src) => (
                      <a
                        key={src.id}
                        href={src.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-start space-x-2 p-2 rounded-lg bg-slate-900/60 border border-slate-800 text-xs"
                      >
                        <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-400 font-bold shrink-0">
                          [{src.id}]
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="font-medium text-slate-300 truncate">{src.title}</p>
                          <span className="text-[10px] text-slate-500">{getDomain(src.url)}</span>
                        </div>
                      </a>
                    ))}
                  </div>
                </div>
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
