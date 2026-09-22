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
  Cpu,
  Layers,
  ChevronRight,
} from 'lucide-react';
import { ChatSessionSummary } from '../../types/api';

interface SidebarProps {
  activeView: string;
  onSelectView: (view: string) => void;
  sessions: ChatSessionSummary[];
  activeSessionId?: string;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
  onDeleteSession: (sessionId: string, e: React.MouseEvent) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeView,
  onSelectView,
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
}) => {
  const navItems = [
    { id: 'dashboard', label: 'Market Dashboard', icon: LayoutDashboard, badge: 'Live' },
    { id: 'chat', label: 'AI Search & Chat', icon: MessageSquare, badge: 'SSE' },
    { id: 'document', label: 'Document Analyzer', icon: FileText, badge: 'Multimodal' },
    { id: 'research', label: 'Deep Equity Research', icon: BarChart3, badge: 'PDF' },
    { id: 'sentiment', label: 'Reddit Sentiment', icon: TrendingUp, badge: 'Keyless' },
    { id: 'stocks', label: 'Stock Inspector', icon: Search, badge: 'Realtime' },
  ];

  return (
    <aside className="w-64 sm:w-72 bg-[#090E18] border-r border-slate-800/80 flex flex-col h-screen select-none shrink-0 sticky top-0">
      {/* 1. Brand Logo */}
      <div className="p-4 border-b border-slate-800/70 flex items-center justify-between">
        <div className="flex items-center space-x-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-sky-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-sky-500/20 text-white font-bold">
            <Cpu className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-1.5">
              <span className="font-bold tracking-tight text-white text-base">MarketMind</span>
              <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-sky-500/20 text-sky-400 font-semibold border border-sky-500/30">
                v2.0
              </span>
            </div>
            <p className="text-[11px] text-slate-400">Institutional AI Terminal</p>
          </div>
        </div>
      </div>

      {/* 2. New Chat Action */}
      <div className="p-3">
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center space-x-2 py-2 px-3 rounded-lg bg-gradient-to-r from-sky-500 to-blue-600 hover:from-sky-400 hover:to-blue-500 text-white font-semibold text-xs transition shadow-md shadow-sky-500/20 active:scale-[0.98]"
        >
          <PlusCircle className="w-4 h-4" />
          <span>New AI Conversation</span>
        </button>
      </div>

      {/* 3. Terminal Navigation Items */}
      <div className="px-3 py-2">
        <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500 px-2 mb-1.5 font-semibold">
          Terminal Views
        </div>
        <nav className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeView === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onSelectView(item.id)}
                className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition group ${
                  isActive
                    ? 'bg-sky-500/15 text-sky-400 border border-sky-500/30 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                }`}
              >
                <div className="flex items-center space-x-2.5">
                  <Icon
                    className={`w-4 h-4 ${
                      isActive ? 'text-sky-400' : 'text-slate-400 group-hover:text-slate-200'
                    }`}
                  />
                  <span>{item.label}</span>
                </div>
                {item.badge && (
                  <span
                    className={`text-[9px] font-mono px-1.5 py-0.5 rounded ${
                      isActive
                        ? 'bg-sky-400/20 text-sky-300'
                        : 'bg-slate-800 text-slate-400 group-hover:text-slate-300'
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
      <div className="flex-1 flex flex-col min-h-0 px-3 py-2 border-t border-slate-800/60 mt-2">
        <div className="flex items-center justify-between px-2 mb-1.5">
          <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500 font-semibold">
            Recent Conversations
          </span>
          <span className="text-[10px] font-mono text-slate-600">{sessions.length}</span>
        </div>

        <div className="flex-1 overflow-y-auto space-y-1 pr-1">
          {sessions.length === 0 ? (
            <div className="px-3 py-6 text-center text-slate-500 text-xs">
              <MessageSquare className="w-6 h-6 mx-auto mb-2 opacity-30 text-slate-400" />
              <span>No past conversations</span>
              <p className="text-[10px] text-slate-600 mt-1">Queries persist automatically</p>
            </div>
          ) : (
            sessions.map((sess) => {
              const isSelected = activeSessionId === sess.session_id;
              return (
                <div
                  key={sess.session_id}
                  onClick={() => onSelectSession(sess.session_id)}
                  className={`group relative flex items-center justify-between px-2.5 py-2 rounded-lg cursor-pointer text-xs transition border ${
                    isSelected
                      ? 'bg-slate-800/80 text-sky-300 border-slate-700'
                      : 'hover:bg-slate-800/40 text-slate-400 hover:text-slate-200 border-transparent'
                  }`}
                >
                  <div className="flex items-center space-x-2 truncate pr-6">
                    <MessageSquare className="w-3.5 h-3.5 shrink-0 opacity-60" />
                    <span className="truncate">{sess.title || 'Conversation'}</span>
                  </div>

                  <button
                    onClick={(e) => onDeleteSession(sess.session_id, e)}
                    title="Delete conversation"
                    className="absolute right-2 opacity-0 group-hover:opacity-100 p-1 hover:text-rose-400 text-slate-500 rounded transition"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* 5. Footer: System Info */}
      <div className="p-3 border-t border-slate-800/70 bg-[#070B13] text-[11px] text-slate-500">
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center space-x-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
            <span className="text-slate-400">Free Tier Guard</span>
          </div>
          <span className="font-mono text-[10px] text-emerald-400">&lt;512 MB RAM</span>
        </div>
        <p className="text-[10px] text-slate-600">Zero Login • Device UUID Isolated</p>
      </div>
    </aside>
  );
};
