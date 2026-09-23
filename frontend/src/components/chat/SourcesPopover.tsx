import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, ExternalLink, Globe, BookOpen } from 'lucide-react';
import { SourceCitation } from '../../types/api';
import { getDomain } from '../../lib/utils';

interface SourcesPopoverProps {
  sources: SourceCitation[];
}

export const SourcesPopover: React.FC<SourcesPopoverProps> = ({ sources }) => {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  if (!sources || sources.length === 0) return null;

  const previewSources = sources.slice(0, 3);

  return (
    <div
      ref={containerRef}
      className="relative inline-block text-left pt-2 select-none"
      onMouseEnter={() => setIsOpen(true)}
      onMouseLeave={() => setIsOpen(false)}
    >
      {/* Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex items-center space-x-2 px-3 py-1.5 rounded-full bg-[#1d1a1e] hover:bg-[#2e2830] border border-[#3d363f] hover:border-[#9013fe]/60 transition shadow-sm group"
      >
        {/* Overlapping First 3 Favicon Previews */}
        <div className="flex items-center -space-x-1.5">
          {previewSources.map((src, i) => {
            const domain = getDomain(src.url);
            const faviconUrl = `https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=64`;
            return (
              <div
                key={src.id || i}
                className="w-5 h-5 rounded-full bg-[#221f23] border border-[#3d363f] flex items-center justify-center p-0.5 overflow-hidden ring-1 ring-[#1d1a1e]"
                title={domain}
              >
                <img
                  src={faviconUrl}
                  alt={domain}
                  className="w-3.5 h-3.5 object-contain rounded-full"
                  onError={(e) => {
                    const target = e.currentTarget;
                    target.style.display = 'none';
                    if (target.nextElementSibling) {
                      (target.nextElementSibling as HTMLElement).style.display = 'block';
                    }
                  }}
                />
                <Globe className="w-2.5 h-2.5 text-slate-400 hidden" />
              </div>
            );
          })}
        </div>

        {/* Label */}
        <span className="text-xs font-semibold text-slate-300 group-hover:text-white transition">
          Sources ({sources.length})
        </span>

        <ChevronDown
          className={`w-3.5 h-3.5 text-slate-400 group-hover:text-[#d8b4fe] transition-transform duration-200 ${
            isOpen ? 'rotate-180' : ''
          }`}
        />
      </button>

      {/* Expanded Sources Dropdown Box */}
      {isOpen && (
        <div className="absolute left-0 bottom-full mb-2 w-80 sm:w-96 rounded-xl bg-[#1d1a1e] border border-[#3d363f] shadow-2xl z-50 overflow-hidden animate-in fade-in zoom-in-95 duration-150">
          <div className="px-3.5 py-2.5 bg-[#221f23] border-b border-[#3d363f] flex items-center justify-between">
            <div className="flex items-center space-x-1.5 text-xs font-semibold text-slate-200">
              <BookOpen className="w-3.5 h-3.5 text-[#c084fc]" />
              <span>Cited Web Sources ({sources.length})</span>
            </div>
            <span className="text-[10px] font-mono text-slate-400">Click to open</span>
          </div>

          <div className="p-2 space-y-1 max-h-64 overflow-y-auto">
            {sources.map((src, idx) => {
              const domain = getDomain(src.url);
              const faviconUrl = `https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=64`;
              return (
                <a
                  key={src.id || idx}
                  href={src.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-start space-x-2.5 p-2 rounded-lg hover:bg-[#2a262b] transition group text-left"
                >
                  <div className="w-5 h-5 rounded bg-[#221f23] border border-[#3d363f] flex items-center justify-center shrink-0 mt-0.5 p-0.5">
                    <img
                      src={faviconUrl}
                      alt={domain}
                      className="w-3.5 h-3.5 object-contain rounded-xs"
                      onError={(e) => {
                        const target = e.currentTarget;
                        target.style.display = 'none';
                        if (target.nextElementSibling) {
                          (target.nextElementSibling as HTMLElement).style.display = 'block';
                        }
                      }}
                    />
                    <Globe className="w-3 h-3 text-slate-400 hidden" />
                  </div>

                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium text-slate-200 group-hover:text-[#d8b4fe] transition line-clamp-1">
                      {src.title || domain}
                    </p>
                    <div className="flex items-center space-x-1.5 text-[10px] text-slate-400 mt-0.5">
                      <span className="font-mono text-[#d8b4fe]/80">[{src.id || idx + 1}]</span>
                      <span className="truncate">{domain}</span>
                    </div>
                  </div>

                  <ExternalLink className="w-3 h-3 text-slate-500 group-hover:text-white opacity-60 group-hover:opacity-100 shrink-0 mt-1 transition" />
                </a>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
