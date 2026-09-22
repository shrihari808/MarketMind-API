import React, { useState, useRef } from 'react';
import {
  UploadCloud,
  FileText,
  Sparkles,
  Send,
  Loader2,
  AlertCircle,
  FileCheck,
  CheckCircle,
} from 'lucide-react';
import { useSSEStream } from '../../hooks/useSSEStream';

interface DocumentAnalyzerViewProps {
  clientId: string;
}

export const DocumentAnalyzerView: React.FC<DocumentAnalyzerViewProps> = ({ clientId }) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [filePreviewUrl, setFilePreviewUrl] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [history, setHistory] = useState<Array<{ role: 'user' | 'assistant'; text: string }>>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const {
    isStreaming,
    statusMessage,
    streamedText,
    error,
    startStream,
  } = useSSEStream(clientId);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (file.type !== 'application/pdf') {
        alert('Please select a valid PDF file.');
        return;
      }
      setSelectedFile(file);
      setFilePreviewUrl(URL.createObjectURL(file));
      setHistory([]);
    }
  };

  const handleAskQuestion = (questionText: string) => {
    if (!selectedFile || !questionText.trim() || isStreaming) return;

    setHistory((prev) => [...prev, { role: 'user', text: questionText }]);
    setQuery('');

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('query', questionText);

    startStream({
      endpoint: '/api/v2/rag/document',
      body: formData,
      isFormData: true,
      onComplete: (fullText) => {
        setHistory((prev) => [...prev, { role: 'assistant', text: fullText }]);
      },
    });
  };

  const handleGenerateSummary = () => {
    if (!selectedFile || isStreaming) return;

    setHistory((prev) => [...prev, { role: 'user', text: 'Generate Executive Financial Summary' }]);

    const formData = new FormData();
    formData.append('file', selectedFile);

    startStream({
      endpoint: '/api/v2/rag/document/summary',
      body: formData,
      isFormData: true,
      onComplete: (fullText) => {
        setHistory((prev) => [...prev, { role: 'assistant', text: fullText }]);
      },
    });
  };

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col space-y-4 pb-4">
      {/* View Header */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div className="flex items-center space-x-2.5">
          <div className="p-2 rounded-lg bg-sky-500/10 text-sky-400 border border-sky-500/20">
            <FileText className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white">Multimodal Financial Document Analyzer</h1>
            <p className="text-xs text-slate-400">
              Direct PDF ingestion into Gemini's 1M+ token window • Zero OCR • Chart & Table native comprehension
            </p>
          </div>
        </div>

        {selectedFile && (
          <button
            onClick={() => fileInputRef.current?.click()}
            className="text-xs px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition"
          >
            Change Document
          </button>
        )}
      </div>

      {!selectedFile ? (
        /* Upload Area */
        <div className="flex-1 flex flex-col items-center justify-center border-2 border-dashed border-slate-800 hover:border-sky-500/50 rounded-2xl p-8 bg-[#0A101D] transition text-center max-w-2xl mx-auto w-full my-auto">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,application/pdf"
            onChange={handleFileChange}
            className="hidden"
          />
          <div className="w-16 h-16 rounded-2xl bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400 mb-4 shadow-lg shadow-sky-500/10">
            <UploadCloud className="w-8 h-8" />
          </div>
          <h2 className="text-base font-bold text-white mb-1">
            Upload Financial Report or Investor Presentation (PDF)
          </h2>
          <p className="text-xs text-slate-400 max-w-sm mb-6">
            Drag & drop your 10-K, 10-Q, annual report, or investor pitch deck. Gemini will read charts, tables, and disclosures natively.
          </p>
          <button
            onClick={() => fileInputRef.current?.click()}
            className="px-5 py-2.5 rounded-xl bg-sky-500 hover:bg-sky-400 text-white font-semibold text-xs transition shadow-md shadow-sky-500/20"
          >
            Select PDF Document
          </button>
        </div>
      ) : (
        /* Split Screen Workspace */
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-4 min-h-0">
          {/* Left: Document Information & Quick Actions */}
          <div className="rounded-xl bg-[#0E1626] border border-slate-800/80 flex flex-col overflow-hidden">
            <div className="p-3.5 border-b border-slate-800 bg-[#0A101D] flex items-center justify-between">
              <div className="flex items-center space-x-2 truncate">
                <FileCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                <span className="text-xs font-semibold text-slate-200 truncate">{selectedFile.name}</span>
              </div>
              <span className="text-[11px] font-mono text-slate-500 shrink-0">
                {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
              </span>
            </div>

            {/* Quick Action Buttons */}
            <div className="p-3 bg-slate-900/60 border-b border-slate-800/60 flex items-center space-x-2 overflow-x-auto text-xs">
              <button
                onClick={handleGenerateSummary}
                disabled={isStreaming}
                className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-sky-500/15 hover:bg-sky-500/25 text-sky-400 border border-sky-500/30 transition shrink-0 disabled:opacity-50"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Executive Summary</span>
              </button>
              <button
                onClick={() => handleAskQuestion('Analyze the balance sheet, cash reserves, and debt levels from this report.')}
                disabled={isStreaming}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition shrink-0 disabled:opacity-50"
              >
                Balance Sheet Moat
              </button>
              <button
                onClick={() => handleAskQuestion('What are the primary risk factors disclosed in this document?')}
                disabled={isStreaming}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition shrink-0 disabled:opacity-50"
              >
                Major Risks
              </button>
            </div>

            {/* In-Browser PDF Preview Iframe */}
            <div className="flex-1 bg-slate-950 p-2 overflow-hidden">
              {filePreviewUrl ? (
                <iframe
                  src={filePreviewUrl}
                  title="PDF Preview"
                  className="w-full h-full rounded border border-slate-800"
                />
              ) : (
                <div className="flex items-center justify-center h-full text-xs text-slate-600">
                  Preview unavailable
                </div>
              )}
            </div>
          </div>

          {/* Right: Interactive Gemini Q&A Chat */}
          <div className="rounded-xl bg-[#0E1626] border border-slate-800/80 flex flex-col overflow-hidden">
            <div className="p-3 border-b border-slate-800 bg-[#0A101D] text-xs font-semibold text-slate-300 flex items-center space-x-2">
              <Sparkles className="w-3.5 h-3.5 text-sky-400" />
              <span>Gemini Multimodal Q&A</span>
            </div>

            {/* Conversation Flow */}
            <div className="flex-1 p-4 overflow-y-auto space-y-4">
              {history.length === 0 && !isStreaming && (
                <div className="text-center py-12 text-slate-500 text-xs">
                  <p>Document loaded and ready for multimodal queries.</p>
                  <p className="text-[11px] text-slate-600 mt-1">
                    Click "Executive Summary" above or ask any question below.
                  </p>
                </div>
              )}

              {history.map((turn, i) => (
                <div
                  key={i}
                  className={`p-3.5 rounded-xl text-xs leading-relaxed whitespace-pre-wrap ${
                    turn.role === 'user'
                      ? 'bg-sky-600/20 border border-sky-500/30 text-sky-200 ml-8'
                      : 'bg-slate-900 border border-slate-800 text-slate-200 mr-4'
                  }`}
                >
                  <div className="text-[10px] font-mono text-slate-400 mb-1 font-semibold">
                    {turn.role === 'user' ? 'YOU' : 'GEMINI 2.0 FLASH'}
                  </div>
                  {turn.text}
                </div>
              ))}

              {isStreaming && (
                <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 mr-4 space-y-2">
                  <div className="flex items-center space-x-2 text-sky-400 font-mono text-[10px]">
                    <Loader2 className="w-3 h-3 animate-spin" />
                    <span>{statusMessage || 'Analyzing document...'}</span>
                  </div>
                  <div className="whitespace-pre-wrap">{streamedText}</div>
                </div>
              )}

              {error && (
                <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-500/40 text-xs text-rose-300 flex items-center space-x-2">
                  <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
                  <span>{error}</span>
                </div>
              )}
            </div>

            {/* Document Query Input */}
            <div className="p-3 border-t border-slate-800 bg-[#0A101D] flex items-center space-x-2">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleAskQuestion(query);
                }}
                disabled={isStreaming}
                placeholder="Ask anything about charts, revenue, or disclosures..."
                className="flex-1 bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-sky-500"
              />
              <button
                onClick={() => handleAskQuestion(query)}
                disabled={!query.trim() || isStreaming}
                className="p-2 rounded-lg bg-sky-500 hover:bg-sky-400 text-white disabled:opacity-40 transition"
              >
                <Send className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
