import React from 'react';
import {
  LayoutDashboard,
  MessageSquare,
  FileText,
  BarChart3,
  TrendingUp,
  Search,
  PlusCircle,
  Trash2,
  ChevronLeft,
  ChevronRight,
  X,
  Copy,
  Check,
} from 'lucide-react';
import { ChatSessionSummary } from '../../types/api';
import logoImg from '../../assets/logo.png';

interface SidebarProps {
  activeView: string;
  onSelectView: (view: string) => void;
  sessions: ChatSessionSummary[];
  activeSessionId?: string;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
  onDeleteSession: (sessionId: string, e: React.MouseEvent) => void;
  clientId?: string;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
  isMobileOpen?: boolean;
  onCloseMobile?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeView,
  onSelectView,
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  clientId,
  isCollapsed = false,
  onToggleCollapse,
  isMobileOpen = false,
  onCloseMobile,
}) => {
  const [copied, setCopied] = React.useState(false);

  const copyClientId = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (clientId) {
      navigator.clipboard.writeText(clientId);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const navItems = [
    { id: 'dashboard', label: 'Market Dashboard', icon: LayoutDashboard, badge: 'Live' },
    { id: 'chat', label: 'AI Search & Chat', icon: MessageSquare },
    { id: 'document', label: 'Document Analyzer', icon: FileText, badge: 'Multimodal' },
    { id: 'research', label: 'Deep Equity Research', icon: BarChart3 },
    { id: 'sentiment', label: 'Reddit Sentiment', icon: TrendingUp },
    { id: 'stocks', label: 'Stock Inspector', icon: Search, badge: 'Realtime' },
  ];

  const sidebarContent = (
    <div className="flex flex-col h-full bg-[#221f23] border-r border-[#3d363f] select-none">
      {/* 1. Brand Logo */}
      <div className="py-2 px-3 border-b border-[#3d363f] flex items-center justify-between min-h-[64px]">
        <div className="flex items-center space-x-3 overflow-hidden">
          <img
            src={logoImg}
            alt="MarketMind Logo"
            className="w-12 h-12 sm:w-14 sm:h-14 object-contain shrink-0 drop-shadow"
          />
          {!isCollapsed && (
            <div className="min-w-0">
              <span className="font-bold tracking-tight text-white text-lg truncate block leading-tight">
                MarketMind
              </span>
            </div>
          )}
        </div>

        {/* Mobile Close Button */}
        {isMobileOpen && (
          <button
            onClick={onCloseMobile}
            className="lg:hidden p-1 rounded-lg text-slate-400 hover:text-white hover:bg-[#3d363f]"
          >
            <X className="w-5 h-5" />
          </button>
        )}

        {/* Desktop Collapse Toggle */}
        {!isMobileOpen && onToggleCollapse && (
          <button
            onClick={onToggleCollapse}
            title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="hidden lg:flex p-1 rounded-lg text-slate-400 hover:text-white hover:bg-[#3d363f] transition"
          >
            {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
        )}
      </div>

      {/* 2. New Chat Action */}
      <div className="p-2.5">
        <button
          onClick={() => {
            onNewChat();
            if (isMobileOpen && onCloseMobile) onCloseMobile();
          }}
          title="New AI Conversation"
          className={`w-full flex items-center justify-center space-x-2 py-2 px-2.5 rounded-lg bg-[#9013fe] hover:bg-[#7c0fd8] text-white font-semibold text-xs transition shadow-md shadow-[#9013fe]/20 active:scale-[0.98] ${
            isCollapsed ? 'px-0' : ''
          }`}
        >
          <PlusCircle className="w-4 h-4 shrink-0" />
          {!isCollapsed && <span className="truncate">New AI Conversation</span>}
        </button>
      </div>

      {/* 3. Terminal Navigation Items */}
      <div className="px-2.5 py-2">
        {!isCollapsed && (
          <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 px-2 mb-1.5 font-semibold">
            Terminal Views
          </div>
        )}
        <nav className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeView === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  onSelectView(item.id);
                  if (isMobileOpen && onCloseMobile) onCloseMobile();
                }}
                title={item.label}
                className={`w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-xs font-medium transition group ${
                  isActive
                    ? 'bg-[#9013fe]/20 text-[#d8b4fe] border border-[#9013fe]/40 shadow-sm'
                    : 'text-slate-300 hover:text-white hover:bg-[#3d363f]'
                }`}
              >
                <div className="flex items-center space-x-2.5 min-w-0">
                  <Icon
                    className={`w-4 h-4 shrink-0 ${
                      isActive ? 'text-[#c084fc]' : 'text-slate-400 group-hover:text-slate-200'
                    }`}
                  />
                  {!isCollapsed && <span className="truncate">{item.label}</span>}
                </div>
                {!isCollapsed && item.badge && (
                  <span
                    className={`text-[9px] font-mono px-1.5 py-0.5 rounded shrink-0 ${
                      isActive
                        ? 'bg-[#9013fe]/30 text-[#d8b4fe]'
                        : 'bg-[#1d1a1e] text-slate-400 group-hover:text-slate-300'
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* 4. Chat History / Sessions Section */}
      {!isCollapsed && (
        <div className="flex-1 flex flex-col min-h-0 px-2.5 py-2 border-t border-[#3d363f] mt-1">
          <div className="flex items-center justify-between px-2 mb-1.5">
            <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 font-semibold">
              Recent Conversations
            </span>
            <span className="text-[10px] font-mono text-slate-500">{sessions.length}</span>
          </div>

          <div className="flex-1 overflow-y-auto space-y-1 pr-1">
            {sessions.length === 0 ? (
              <div className="px-3 py-6 text-center text-slate-400 text-xs">
                <MessageSquare className="w-5 h-5 mx-auto mb-1.5 opacity-40 text-slate-400" />
                <span>No past conversations</span>
                <p className="text-[10px] text-slate-500 mt-0.5">Queries persist automatically</p>
              </div>
            ) : (
              sessions.map((sess) => {
                const isSelected = activeSessionId === sess.session_id;
                return (
                  <div
                    key={sess.session_id}
                    onClick={() => {
                      onSelectSession(sess.session_id);
                      if (isMobileOpen && onCloseMobile) onCloseMobile();
                    }}
                    className={`group relative flex items-center justify-between px-2.5 py-2 rounded-lg cursor-pointer text-xs transition border ${
                      isSelected
                        ? 'bg-[#1d1a1e] text-[#d8b4fe] border-[#3d363f]'
                        : 'hover:bg-[#3d363f]/60 text-slate-300 hover:text-white border-transparent'
                    }`}
                  >
                    <div className="flex items-center space-x-2 truncate pr-6">
                      <MessageSquare className="w-3.5 h-3.5 shrink-0 opacity-60 text-slate-400" />
                      <span className="truncate">{sess.title || 'Conversation'}</span>
                    </div>

                    <button
                      onClick={(e) => onDeleteSession(sess.session_id, e)}
                      title="Delete conversation"
                      className="absolute right-2 opacity-0 group-hover:opacity-100 p-1 hover:text-rose-400 text-slate-400 rounded transition"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* 5. Footer: System Info & Device UUID */}
      <div className="p-3 border-t border-[#3d363f] bg-[#1d1a1e] text-[11px] text-slate-400 mt-auto">
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center space-x-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 shrink-0"></span>
            {!isCollapsed && <span className="text-slate-300 truncate">Free Tier Guard</span>}
          </div>
          {!isCollapsed && <span className="font-mono text-[10px] text-emerald-400 shrink-0">&lt;512 MB</span>}
        </div>
        {!isCollapsed && (
          <div className="flex items-center justify-between text-[10px] text-slate-400 pt-1 border-t border-[#3d363f]/50">
            <span className="text-slate-400 truncate">Zero Login • Device UUID</span>
            {clientId && (
              <button
                type="button"
                onClick={copyClientId}
                title={`Device UUID: ${clientId} (Click to copy)`}
                className="font-mono text-[#d8b4fe] hover:text-white flex items-center space-x-1 transition ml-1 shrink-0 bg-[#221f23] px-1.5 py-0.5 rounded border border-[#3d363f]/60 hover:border-[#9013fe]"
              >
                <span>{clientId.slice(0, 8)}...</span>
                {copied ? <Check className="w-2.5 h-2.5 text-emerald-400" /> : <Copy className="w-2.5 h-2.5 text-slate-400" />}
              </button>
            )}
          </div>
        )}

        {/* 6. Creator & GitHub Repo Link */}
        {!isCollapsed && (
          <div className="flex items-center justify-between text-[10px] text-slate-400 pt-1 mt-1 border-t border-[#3d363f]/40">
            <span className="text-slate-400 truncate">
              Created by Shrihari &copy; 2026
            </span>
            <a
              href="https://github.com/shrihari808/MarketMind-API"
              target="_blank"
              rel="noopener noreferrer"
              title="Repo"
              className="text-slate-400 hover:text-white transition p-0.5 rounded hover:bg-[#3d363f]/60 shrink-0"
              aria-label="Repo"
            >
              <svg
                className="w-3.5 h-3.5 fill-current"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  fillRule="evenodd"
                  clipRule="evenodd"
                  d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
                />
              </svg>
            </a>
          </div>
        )}
        {isCollapsed && (
          <div className="flex justify-center pt-1.5 mt-1 border-t border-[#3d363f]/40">
            <a
              href="https://github.com/shrihari808/MarketMind-API"
              target="_blank"
              rel="noopener noreferrer"
              title="Repo"
              className="text-slate-400 hover:text-white transition p-1 rounded hover:bg-[#3d363f]"
              aria-label="Repo"
            >
              <svg
                className="w-3.5 h-3.5 fill-current"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  fillRule="evenodd"
                  clipRule="evenodd"
                  d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
                />
              </svg>
            </a>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Sidebar */}
      <aside
        className={`hidden lg:flex flex-col h-screen select-none shrink-0 sticky top-0 transition-all duration-200 z-30 ${
          isCollapsed ? 'w-16' : 'w-64 xl:w-72'
        }`}
      >
        {sidebarContent}
      </aside>

      {/* Mobile Offcanvas Drawer */}
      {isMobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
            onClick={onCloseMobile}
          />
          <div className="relative w-72 max-w-[85vw] h-full shadow-2xl z-10 animate-in slide-in-from-left duration-200">
            {sidebarContent}
          </div>
        </div>
      )}
    </>
  );
};
