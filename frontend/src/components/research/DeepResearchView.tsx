import React, { useState } from 'react';
import {
  BarChart3,
  Download,
  Loader2,
  FileText,
  Building2,
  Calendar,
  AlertTriangle,
  Sparkles,
} from 'lucide-react';
import { DeepResearchReport } from '../../types/api';
import { api } from '../../lib/api';
import { MarkdownRenderer } from '../common/MarkdownRenderer';

interface DeepResearchViewProps {
  clientId: string;
}

export const DeepResearchView: React.FC<DeepResearchViewProps> = ({ clientId }) => {
  const [ticker, setTicker] = useState('RELIANCE.NS');
  const [country, setCountry] = useState<'IN' | 'US'>('IN');
  const [sectionBySection, setSectionBySection] = useState(false);
  const [report, setReport] = useState<DeepResearchReport | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isDownloadingPdf, setIsDownloadingPdf] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    if (!ticker.trim() || isGenerating) return;
    setIsGenerating(true);
    setError(null);

    try {
      const data = await api.generateResearchReport(ticker.trim(), country, sectionBySection, clientId);
      setReport(data);
    } catch (err: any) {
      setError(err.message || 'Failed to generate equity research report.');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDownloadPdf = async () => {
    if (!ticker.trim() || isDownloadingPdf) return;
    setIsDownloadingPdf(true);
    try {
      await api.downloadResearchPdf(ticker.trim(), country, sectionBySection, clientId);
    } catch (err: any) {
      alert(`PDF Download Error: ${err.message}`);
    } finally {
      setIsDownloadingPdf(false);
    }
  };

  return (
    <div className="space-y-6 pb-28 max-w-5xl mx-auto">
      {/* Header */}
      <div className="pb-4 border-b border-[#383A40]">
        <div className="flex items-center space-x-2.5">
          <div className="p-2 rounded-lg bg-[#9013fe]/10 text-[#d8b4fe] border border-[#9013fe]/30">
            <BarChart3 className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">Institutional Equity Research Pipeline</h1>
            <p className="text-xs text-slate-400">
              Synthesizes 7-section institutional reports using fundamentals, live web searches, and in-memory ReportLab PDF compilation
            </p>
          </div>
        </div>
      </div>

      {/* Control Panel */}
      <div className="p-4 rounded-xl bg-[#2B2D31] border border-[#383A40] shadow-md">
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 items-end">
          <div>
            <label className="block text-[11px] font-mono text-slate-400 mb-1">MARKET REGION</label>
            <select
              value={country}
              onChange={(e) => {
                const c = e.target.value as 'IN' | 'US';
                setCountry(c);
                if (c === 'IN' && ticker === 'NVDA') setTicker('RELIANCE.NS');
                if (c === 'US' && ticker === 'RELIANCE.NS') setTicker('NVDA');
              }}
              className="w-full bg-[#1E1F22] border border-[#383A40] rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-[#9013fe]"
            >
              <option value="IN">🇮🇳 India (NSE / BSE)</option>
              <option value="US">🇺🇸 United States (NYSE / NASDAQ)</option>
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-mono text-slate-400 mb-1">STOCK TICKER</label>
            <input
              type="text"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              placeholder="e.g. RELIANCE.NS, NVDA, AAPL"
              className="w-full bg-[#1E1F22] border border-[#383A40] rounded-lg px-3 py-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-[#9013fe] uppercase placeholder-slate-500"
            />
          </div>

          <div className="flex items-center space-x-2 pb-2">
            <input
              type="checkbox"
              id="sectionBySection"
              checked={sectionBySection}
              onChange={(e) => setSectionBySection(e.target.checked)}
              className="rounded bg-[#1E1F22] border-[#383A40] text-[#9013fe] focus:ring-[#9013fe] w-4 h-4 cursor-pointer"
            />
            <label htmlFor="sectionBySection" className="text-xs text-slate-300 cursor-pointer select-none">
              Modular 7-Pass Mode
            </label>
          </div>

          <div>
            <button
              onClick={handleGenerate}
              disabled={isGenerating || !ticker.trim()}
              className="w-full flex items-center justify-center space-x-1.5 py-2 px-4 rounded-lg bg-[#9013fe] hover:bg-[#7c0fd8] text-white font-semibold text-xs transition disabled:opacity-50 shadow-md shadow-[#9013fe]/20"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Synthesizing...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Generate Report</span>
                </>
              )}
            </button>
          </div>
        </div>

        {error && (
          <div className="mt-3 p-3 rounded-lg bg-rose-950/30 border border-rose-500/30 text-xs text-rose-300 flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* Report Display */}
      {report ? (
        <div className="rounded-xl bg-[#2B2D31] border border-[#383A40] p-6 space-y-6 shadow-xl">
          {/* Header Metadata */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#383A40]">
            <div>
              <div className="flex items-center space-x-3">
                <span className="font-mono text-xs px-2.5 py-0.5 rounded bg-[#9013fe]/10 text-[#d8b4fe] font-bold border border-[#9013fe]/30">
                  {report.ticker}
                </span>
                <h2 className="text-xl font-bold text-white tracking-tight">{report.company_name}</h2>
              </div>
              <p className="text-xs text-slate-400 mt-1 flex items-center space-x-2">
                <Building2 className="w-3.5 h-3.5 text-slate-400" />
                <span>MarketMind Institutional Equity Research Coverage</span>
              </p>
            </div>

            <div className="flex items-center space-x-3">
              <div className="flex items-center space-x-1.5 text-xs text-slate-400 font-mono">
                <Calendar className="w-3.5 h-3.5 text-slate-400" />
                <span>{new Date(report.generated_at).toLocaleDateString()}</span>
              </div>

              <button
                onClick={handleDownloadPdf}
                disabled={isDownloadingPdf}
                className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-xs font-semibold transition"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Download PDF</span>
              </button>
            </div>
          </div>

          {/* Report Markdown Content */}
          <div className="text-slate-200 text-xs leading-relaxed space-y-4 font-sans">
            <MarkdownRenderer content={report.report_markdown} />
          </div>
        </div>
      ) : (
        !isGenerating && (
          <div className="p-12 text-center border border-dashed border-[#383A40] rounded-xl bg-[#1E1F22] text-slate-400 text-xs">
            <FileText className="w-8 h-8 mx-auto mb-2 opacity-40 text-slate-400" />
            <p className="font-medium text-slate-300">No report generated yet</p>
            <p className="text-[11px] text-slate-400 mt-1">
              Select a ticker above and click "Generate Report" or "Download PDF".
            </p>
          </div>
        )
      )}
    </div>
  );
};
