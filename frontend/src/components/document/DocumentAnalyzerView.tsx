import React, { useState, useRef } from 'react';
import {
  UploadCloud,
  FileText,
  Sparkles,
  Send,
  Loader2,
  AlertCircle,
  FileCheck,
} from 'lucide-react';
import { useSSEStream } from '../../hooks/useSSEStream';
import { MarkdownRenderer } from '../common/MarkdownRenderer';

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
    <div className="flex-1 flex flex-col space-y-4 pb-28 max-w-6xl mx-auto w-full">
      {/* View Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#383A40]">
        <div className="flex items-center space-x-2.5">
          <div className="p-2 rounded-lg bg-[#9013fe]/10 text-[#d8b4fe] border border-[#9013fe]/30">
            <FileText className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white">Multimodal Financial Document Analyzer</h1>
            <p className="text-xs text-slate-400">
              Direct PDF ingestion • Zero OCR • Native Chart & Table Comprehension
            </p>
          </div>
        </div>

        {selectedFile && (
          <div className="flex items-center space-x-2">
            <button
              onClick={handleGenerateSummary}
              disabled={isStreaming}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-[#9013fe]/15 hover:bg-[#9013fe]/25 text-[#d8b4fe] border border-[#9013fe]/30 text-xs font-semibold transition disabled:opacity-50"
            >
              <Sparkles className="w-3.5 h-3.5 text-[#c084fc]" />
              <span>Executive Summary</span>
            </button>
            <button
              onClick={() => {
                setSelectedFile(null);
                setFilePreviewUrl(null);
                setHistory([]);
              }}
              className="text-xs text-slate-400 hover:text-slate-200 px-2 py-1 transition"
            >
              Clear
            </button>
          </div>
        )}
      </div>

      {/* Main Content Area */}
      {!selectedFile ? (
        /* Upload Area */
        <div
          onClick={() => fileInputRef.current?.click()}
          className="flex-1 min-h-[350px] border-2 border-dashed border-[#383A40] hover:border-[#9013fe]/60 rounded-2xl bg-[#2B2D31]/50 hover:bg-[#2B2D31] flex flex-col items-center justify-center p-8 transition cursor-pointer text-center group"
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            onChange={handleFileChange}
            className="hidden"
          />
          <div className="w-16 h-16 rounded-2xl bg-[#1E1F22] border border-[#383A40] group-hover:border-[#9013fe]/40 flex items-center justify-center mb-4 text-slate-400 group-hover:text-[#d8b4fe] transition shadow-lg">
            <UploadCloud className="w-8 h-8" />
          </div>
          <h3 className="text-base font-bold text-white mb-1">
            Upload PDF Document
          </h3>
          <p className="text-xs text-slate-400 max-w-sm mb-4 leading-relaxed">
            Drag & drop your 10-K, 10-Q, annual report, or investor pitch deck. The analyzer reads charts, tables, and disclosures natively.
          </p>
          <span className="text-[11px] font-mono px-2.5 py-1 rounded bg-[#1E1F22] border border-[#383A40] text-slate-400">
            PDF files up to 20MB
          </span>
        </div>
      ) : (
        /* Split View: Left Document Preview, Right Conversation */
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-4 min-h-[500px]">
          {/* Left: Document Info & Preview */}
          <div className="rounded-xl bg-[#2B2D31] border border-[#383A40] flex flex-col overflow-hidden">
            <div className="p-3 border-b border-[#383A40] bg-[#1E1F22] flex items-center justify-between text-xs">
              <div className="flex items-center space-x-2 truncate">
                <FileCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                <span className="font-medium text-slate-200 truncate">{selectedFile.name}</span>
              </div>
              <span className="font-mono text-slate-500 text-[10px] shrink-0 ml-2">
                {(selectedFile.size / (1024 * 1024)).toFixed(1)} MB
              </span>
            </div>

            <div className="flex-1 p-2 bg-[#1E1F22]/50 min-h-[350px]">
              {filePreviewUrl ? (
                <iframe
                  src={filePreviewUrl}
                  title="PDF Preview"
                  className="w-full h-full rounded border border-[#383A40]"
                />
              ) : (
                <div className="flex items-center justify-center h-full text-xs text-slate-500">
                  Preview unavailable
                </div>
              )}
            </div>
          </div>

          {/* Right: Interactive Document Q&A Chat */}
          <div className="rounded-xl bg-[#2B2D31] border border-[#383A40] flex flex-col overflow-hidden min-h-[400px]">
            <div className="p-3 border-b border-[#383A40] bg-[#1E1F22] text-xs font-semibold text-slate-300 flex items-center space-x-2">
              <Sparkles className="w-3.5 h-3.5 text-[#c084fc]" />
              <span>Document Intelligence Q&A</span>
            </div>

            {/* Conversation Flow */}
            <div className="flex-1 p-4 overflow-y-auto space-y-4 max-h-[450px]">
              {history.length === 0 && !isStreaming && (
                <div className="text-center py-12 text-slate-500 text-xs">
                  <p className="font-medium text-slate-400">Document loaded and ready for multimodal queries.</p>
                  <p className="text-[11px] text-slate-500 mt-1">
                    Click "Executive Summary" above or ask any question below.
                  </p>
                </div>
              )}

              {history.map((turn, i) => (
                <div
                  key={i}
                  className={`p-3.5 rounded-xl text-xs leading-relaxed ${
                    turn.role === 'user'
                      ? 'bg-[#9013fe]/20 border border-[#9013fe]/40 text-slate-100 ml-6'
                      : 'bg-[#1E1F22] border border-[#383A40] text-slate-200 mr-2'
                  }`}
                >
                  <div className="text-[10px] font-mono text-slate-400 mb-1 font-semibold uppercase">
                    {turn.role === 'user' ? 'YOU' : 'MARKETMIND AI'}
                  </div>
                  <MarkdownRenderer content={turn.text} />
                </div>
              ))}

              {isStreaming && (
                <div className="p-3.5 rounded-xl bg-[#1E1F22] border border-[#383A40] text-xs text-slate-200 mr-2 space-y-2">
                  <div className="flex items-center space-x-2 text-[#c084fc] font-mono text-[10px]">
                    <Loader2 className="w-3 h-3 animate-spin" />
                    <span>{statusMessage || 'Analyzing document...'}</span>
                  </div>
                  <MarkdownRenderer content={streamedText} isStreaming />
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
            <div className="p-3 border-t border-[#383A40] bg-[#1E1F22] flex items-center space-x-2">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleAskQuestion(query);
                }}
                disabled={isStreaming}
                placeholder="Ask anything about charts, revenue, or disclosures..."
                className="flex-1 bg-[#2B2D31] border border-[#383A40] rounded-lg px-3 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-[#9013fe]"
              />
              <button
                onClick={() => handleAskQuestion(query)}
                disabled={!query.trim() || isStreaming}
                className="p-2 rounded-lg bg-[#9013fe] hover:bg-[#7c0fd8] text-white disabled:opacity-30 transition shadow-md shadow-[#9013fe]/20 shrink-0"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
