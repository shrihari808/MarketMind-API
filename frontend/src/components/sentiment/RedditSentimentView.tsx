import React, { useState } from 'react';
import {
  TrendingUp,
  MessageSquare,
  Sparkles,
  Loader2,
  ExternalLink,
  ThumbsUp,
  ThumbsDown,
  AlertCircle,
  HelpCircle,
} from 'lucide-react';
import { RedditSentimentReport } from '../../types/api';
import { api } from '../../lib/api';

interface RedditSentimentViewProps {
  clientId: string;
}

export const RedditSentimentView: React.FC<RedditSentimentViewProps> = ({ clientId }) => {
  const [topic, setTopic] = useState('Tata Motors');
  const [report, setReport] = useState<RedditSentimentReport | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAnalyze = async () => {
    if (!topic.trim() || isLoading) return;
    setIsLoading(true);
    setError(null);

    try {
      const data = await api.getRedditSentiment(topic.trim(), clientId);
      setReport(data);
    } catch (err: any) {
      setError(err.message || 'Failed to analyze Reddit sentiment.');
    } finally {
      setIsLoading(false);
    }
  };

  const getSentimentColor = (sentiment: string) => {
    if (sentiment.toLowerCase().includes('bull')) return 'text-emerald-400 bg-emerald-950/40 border-emerald-500/30';
    if (sentiment.toLowerCase().includes('bear')) return 'text-rose-400 bg-rose-950/40 border-rose-500/30';
    return 'text-amber-400 bg-amber-950/40 border-amber-500/30';
  };

  return (
    <div className="space-y-6 pb-28 max-w-4xl mx-auto">
      {/* Header */}
      <div className="pb-4 border-b border-slate-800">
        <div className="flex items-center space-x-2.5">
          <div className="p-2 rounded-lg bg-orange-500/10 text-orange-400 border border-orange-500/20">
            <MessageSquare className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">Retail Community Sentiment (Reddit)</h1>
            <p className="text-xs text-slate-400">
              Keyless multi-subreddit discovery across r/IndianStockMarket, r/wallstreetbets, and r/stocks
            </p>
          </div>
        </div>
      </div>

      {/* Input Bar */}
      <div className="p-4 rounded-xl bg-[#0E1626] border border-slate-800/80 shadow-md">
        <div className="flex items-center space-x-2">
          <input
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleAnalyze();
            }}
            placeholder="Enter stock name or ticker (e.g. Tata Motors, Nvidia, Reliance)..."
            className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
          />
          <button
            onClick={handleAnalyze}
            disabled={isLoading || !topic.trim()}
            className="flex items-center space-x-1.5 px-4 py-2 rounded-lg bg-orange-600 hover:bg-orange-500 text-white font-semibold text-xs transition disabled:opacity-50 shadow-md shadow-orange-600/20"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Scanning Threads...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5" />
                <span>Analyze Sentiment</span>
              </>
            )}
          </button>
        </div>

        {error && (
          <div className="mt-3 p-3 rounded-lg bg-rose-950/30 border border-rose-500/30 text-xs text-rose-300 flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* Sentiment Analysis Report */}
      {report && (
        <div className="space-y-4">
          {/* Sentiment Summary Card */}
          <div className="p-5 rounded-xl bg-[#0E1626] border border-slate-800/80 shadow-lg">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
              <div>
                <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">
                  COMMUNITY CONSENSUS
                </span>
                <h2 className="text-xl font-bold text-white capitalize mt-0.5">{report.topic}</h2>
              </div>

              <div className="flex items-center space-x-3">
                <div
                  className={`px-3 py-1.5 rounded-lg border font-mono font-bold text-xs uppercase flex items-center space-x-1.5 ${getSentimentColor(
                    report.sentiment
                  )}`}
                >
                  <TrendingUp className="w-4 h-4" />
                  <span>{report.sentiment}</span>
                </div>

                <div className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 font-mono text-xs text-slate-300">
                  Score: <span className="font-bold text-sky-400">{report.sentiment_score.toFixed(2)}</span>
                </div>
              </div>
            </div>

            {/* AI Summary */}
            <p className="text-xs text-slate-300 leading-relaxed font-sans mt-4">
              {report.summary}
            </p>
          </div>

          {/* Bull vs Bear Arguments Breakdown */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Bullish */}
            <div className="p-4 rounded-xl bg-[#0E1626] border border-slate-800/80">
              <div className="flex items-center space-x-2 text-emerald-400 font-semibold text-xs mb-3">
                <ThumbsUp className="w-4 h-4" />
                <span>Bullish Retail Arguments</span>
              </div>
              <ul className="space-y-2">
                {report.bullish_arguments && report.bullish_arguments.length > 0 ? (
                  report.bullish_arguments.map((arg, idx) => (
                    <li key={idx} className="text-xs text-slate-300 flex items-start space-x-2">
                      <span className="text-emerald-400 font-mono font-bold shrink-0">•</span>
                      <span>{arg}</span>
                    </li>
                  ))
                ) : (
                  <p className="text-xs text-slate-500">No major bullish points reported.</p>
                )}
              </ul>
            </div>

            {/* Bearish */}
            <div className="p-4 rounded-xl bg-[#0E1626] border border-slate-800/80">
              <div className="flex items-center space-x-2 text-rose-400 font-semibold text-xs mb-3">
                <ThumbsDown className="w-4 h-4" />
                <span>Bearish Retail Arguments</span>
              </div>
              <ul className="space-y-2">
                {report.bearish_arguments && report.bearish_arguments.length > 0 ? (
                  report.bearish_arguments.map((arg, idx) => (
                    <li key={idx} className="text-xs text-slate-300 flex items-start space-x-2">
                      <span className="text-rose-400 font-mono font-bold shrink-0">•</span>
                      <span>{arg}</span>
                    </li>
                  ))
                ) : (
                  <p className="text-xs text-slate-500">No major bearish points reported.</p>
                )}
              </ul>
            </div>
          </div>

          {/* Scraped Thread Links */}
          {report.thread_links && report.thread_links.length > 0 && (
            <div className="p-4 rounded-xl bg-[#0E1626] border border-slate-800/80">
              <div className="text-xs font-semibold text-slate-400 mb-2 font-mono uppercase tracking-wider">
                Analyzed Discussion Threads ({report.threads_analyzed || report.thread_links.length})
              </div>
              <div className="space-y-1.5">
                {report.thread_links.map((link, idx) => (
                  <a
                    key={idx}
                    href={link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center justify-between p-2 rounded-lg bg-slate-900/60 hover:bg-slate-800 text-xs text-slate-300 hover:text-sky-400 transition"
                  >
                    <span className="truncate max-w-xl">{link}</span>
                    <ExternalLink className="w-3 h-3 opacity-60 shrink-0 ml-2" />
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
