import React, { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { SourceCitation } from '../../types/api';
import { getDomain } from '../../lib/utils';

interface MarkdownRendererProps {
  content: string;
  sources?: SourceCitation[];
  isStreaming?: boolean;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({
  content,
  sources = [],
  isStreaming = false,
}) => {
  // Pre-process content to transform bracket citations [6] or [1, 3] into custom citation markdown links
  const processedContent = useMemo(() => {
    if (!content) return '';

    // Regex matches [1] or [1, 2, 4]
    return content.replace(/\[(\d+(?:\s*,\s*\d+)*)\]/g, (match, idList) => {
      const ids = idList.split(',').map((s: string) => s.trim());
      // Check if at least one ID exists in sources
      const links = ids.map((idStr: string) => {
        const idNum = parseInt(idStr, 10);
        const sourceExists = sources.some((s) => s.id === idNum);
        if (sourceExists) {
          return `[cite:${idStr}](cite:${idStr})`;
        }
        return `[${idStr}]`;
      });
      return links.join(' ');
    });
  }, [content, sources]);

  return (
    <div className="relative text-slate-200 text-sm leading-relaxed font-sans max-w-none break-words">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="text-lg sm:text-xl font-bold text-white mt-5 mb-3 pb-2 border-b border-[#3d363f] tracking-tight">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-base sm:text-lg font-bold text-white mt-4 mb-2 tracking-tight">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-sm sm:text-base font-semibold text-slate-100 mt-3 mb-1.5">
              {children}
            </h3>
          ),
          h4: ({ children }) => (
            <h4 className="text-xs sm:text-sm font-semibold text-slate-200 mt-2 mb-1">
              {children}
            </h4>
          ),
          p: ({ children }) => (
            <p className="mb-3 leading-relaxed text-slate-200 last:mb-0">
              {children}
            </p>
          ),
          ul: ({ children }) => (
            <ul className="list-disc pl-5 mb-3 space-y-1 text-slate-200">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal pl-5 mb-3 space-y-1 text-slate-200">
              {children}
            </ol>
          ),
          li: ({ children }) => (
            <li className="leading-relaxed">
              {children}
            </li>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-4 border-[#9013fe] pl-3 py-1 my-3 bg-[#9013fe]/10 rounded-r text-slate-300 italic">
              {children}
            </blockquote>
          ),
          hr: () => (
            <hr className="border-[#3d363f] my-4" />
          ),
          table: ({ children }) => (
            <div className="overflow-x-auto my-4 rounded-lg border border-[#3d363f]">
              <table className="min-w-full text-left text-xs border-collapse divide-y divide-[#3d363f]">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-[#1d1a1e] text-slate-200 font-semibold">
              {children}
            </thead>
          ),
          th: ({ children }) => (
            <th className="px-3.5 py-2.5 text-xs font-semibold text-slate-200 border-b border-[#3d363f]">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="px-3.5 py-2 text-xs text-slate-300 border-b border-[#3d363f]/60">
              {children}
            </td>
          ),
          strong: ({ children }) => (
            <strong className="font-semibold text-white">
              {children}
            </strong>
          ),
          em: ({ children }) => (
            <em className="text-slate-300 italic">
              {children}
            </em>
          ),
          a: ({ href, children }) => {
            // Handle inline citation links
            if (href?.startsWith('cite:')) {
              const idNum = parseInt(href.replace('cite:', ''), 10);
              const source = sources.find((s) => s.id === idNum);
              if (source) {
                const domain = getDomain(source.url);
                const faviconUrl = `https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=64`;
                return (
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    title={`Source [${idNum}]: ${source.title || domain}\n${source.url}`}
                    className="inline-flex items-center justify-center align-middle mx-1 p-0.5 w-5 h-5 rounded-md bg-[#1d1a1e] hover:bg-[#3d363f] border border-[#3d363f] hover:border-[#9013fe] transition -translate-y-0.5 shadow-xs group"
                  >
                    <img
                      src={faviconUrl}
                      alt={domain}
                      className="w-3.5 h-3.5 object-contain rounded-xs"
                      onError={(e) => {
                        const target = e.currentTarget;
                        target.style.display = 'none';
                        if (target.nextElementSibling) {
                          (target.nextElementSibling as HTMLElement).style.display = 'inline-flex';
                        }
                      }}
                    />
                    <span className="hidden text-[9px] font-mono font-bold text-[#d8b4fe]">
                      {idNum}
                    </span>
                  </a>
                );
              }
            }

            // Normal markdown link
            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[#c084fc] hover:text-[#9013fe] underline underline-offset-2 transition font-medium"
              >
                {children}
              </a>
            );
          },
          code: ({ className, children, ...props }) => {
            const isInline = !className;
            return isInline ? (
              <code
                className="bg-[#1d1a1e] text-[#d8b4fe] border border-[#3d363f] px-1.5 py-0.5 rounded font-mono text-xs"
                {...props}
              >
                {children}
              </code>
            ) : (
              <code className="font-mono text-xs text-slate-200" {...props}>
                {children}
              </code>
            );
          },
          pre: ({ children }) => (
            <pre className="bg-[#1d1a1e] border border-[#3d363f] rounded-xl p-4 my-3 overflow-x-auto font-mono text-xs text-slate-200">
              {children}
            </pre>
          ),
        }}
      >
        {processedContent}
      </ReactMarkdown>
      {isStreaming && (
        <span className="inline-block w-2 h-4 ml-1 bg-[#9013fe] animate-pulse align-middle rounded-xs shadow-sm shadow-[#9013fe]/50" />
      )}
    </div>
  );
};
