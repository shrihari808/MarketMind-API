import React, { useState, useEffect, useCallback } from 'react';
import { Header } from './components/layout/Header';
import { Sidebar } from './components/layout/Sidebar';
import { Omnibar } from './components/omnibar/Omnibar';
import { MarketDashboardView } from './components/dashboard/MarketDashboardView';
import { FinancialChatView } from './components/chat/FinancialChatView';
import { DocumentAnalyzerView } from './components/document/DocumentAnalyzerView';
import { DeepResearchView } from './components/research/DeepResearchView';
import { RedditSentimentView } from './components/sentiment/RedditSentimentView';
import { StockInspectorView } from './components/stocks/StockInspectorView';

import { useClientIdentity } from './hooks/useClientIdentity';
import { useSSEStream } from './hooks/useSSEStream';
import { api } from './lib/api';
import {
  MarketDashboardResponse,
  ChatSessionSummary,
  ChatMessageItem,
  SourceCitation,
} from './types/api';

export function App() {
  // 1. Client Identity & Region State
  const { clientId } = useClientIdentity();
  const [country, setCountry] = useState<'IN' | 'US'>('IN');

  // 2. Active View State ('dashboard' is the landing view)
  const [activeView, setActiveView] = useState<string>('dashboard');

  // 3. Responsive Sidebar State
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);

  // 4. Market Dashboard State
  const [dashboardData, setDashboardData] = useState<MarketDashboardResponse | null>(null);
  const [isDashboardLoading, setIsDashboardLoading] = useState(false);

  // 5. Chat & Conversation State
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>(() => `session-${Date.now()}`);
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);

  // 6. Stock Inspector target ticker
  const [inspectedTicker, setInspectedTicker] = useState('RELIANCE.NS');

  // 7. SSE Streaming Hook for Web RAG
  const {
    isStreaming,
    statusMessage,
    streamedText,
    sources: streamingSources,
    error: streamingError,
    startStream,
    stopStreaming,
  } = useSSEStream(clientId);

  // --- Fetch Dashboard Data ---
  const loadDashboard = useCallback(async (targetCountry: 'IN' | 'US' = country) => {
    setIsDashboardLoading(true);
    try {
      const data = await api.getDashboard(targetCountry, clientId);
      setDashboardData(data);
    } catch (err) {
      console.error('Failed to load dashboard:', err);
    } finally {
      setIsDashboardLoading(false);
    }
  }, [country, clientId]);

  // Load dashboard on initial mount & country switch
  useEffect(() => {
    loadDashboard(country);
  }, [country, loadDashboard]);

  // --- Fetch Chat Sessions ---
  const loadSessions = useCallback(async () => {
    try {
      const data = await api.getSessions(clientId);
      setSessions(data || []);
    } catch (err) {
      console.warn('Could not load sessions:', err);
    }
  }, [clientId]);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  // --- Handle Country Selection ---
  const handleSelectCountry = (newCountry: 'IN' | 'US') => {
    setCountry(newCountry);
    loadDashboard(newCountry);
  };

  // --- Handle Typed Prompt Submission from Omnibar (Stays in active chat) ---
  const handleSubmitPrompt = (promptText: string) => {
    if (!promptText.trim()) return;

    setActiveView('chat');

    const userTurn: ChatMessageItem = {
      role: 'user',
      content: promptText,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userTurn]);

    startStream({
      endpoint: '/api/v2/rag/web',
      body: {
        query: promptText,
        country: country,
        session_id: activeSessionId,
      },
      onComplete: (fullText: string, finalSources: SourceCitation[]) => {
        const assistantTurn: ChatMessageItem = {
          role: 'assistant',
          content: fullText,
          sources: finalSources,
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, assistantTurn]);
        loadSessions();
      },
    });
  };

  // --- Handle Suggested Prompt Click (Spawns a brand new chat session) ---
  const handleSuggestedPrompt = (promptText: string) => {
    if (!promptText.trim()) return;

    const newId = `session-${Date.now()}`;
    setActiveSessionId(newId);
    setActiveView('chat');

    const userTurn: ChatMessageItem = {
      role: 'user',
      content: promptText,
      created_at: new Date().toISOString(),
    };
    setMessages([userTurn]);

    startStream({
      endpoint: '/api/v2/rag/web',
      body: {
        query: promptText,
        country: country,
        session_id: newId,
      },
      onComplete: (fullText: string, finalSources: SourceCitation[]) => {
        const assistantTurn: ChatMessageItem = {
          role: 'assistant',
          content: fullText,
          sources: finalSources,
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, assistantTurn]);
        loadSessions();
      },
    });
  };

  // --- Start Fresh Chat ---
  const handleNewChat = () => {
    const newId = `session-${Date.now()}`;
    setActiveSessionId(newId);
    setMessages([]);
    setActiveView('chat');
  };

  // --- Select Past Session ---
  const handleSelectSession = async (sessionId: string) => {
    setActiveSessionId(sessionId);
    setActiveView('chat');
    try {
      const history = await api.getSessionMessages(sessionId, clientId);
      setMessages(Array.isArray(history) ? history : (history as any)?.messages || []);
    } catch (err) {
      console.error('Failed to load session messages:', err);
      setMessages([]);
    }
  };

  // --- Delete Session ---
  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await api.deleteSession(sessionId, clientId);
      setSessions((prev) => prev.filter((s) => s.session_id !== sessionId));
      if (activeSessionId === sessionId) {
        handleNewChat();
      }
    } catch (err) {
      console.error('Failed to delete session:', err);
    }
  };

  // --- Ticker Selection from Dashboard or Elsewhere ---
  const handleSelectTicker = (ticker: string) => {
    setInspectedTicker(ticker);
    setActiveView('stocks');
  };

  return (
    <div className="flex h-[100dvh] min-h-screen w-screen overflow-hidden bg-[#313338] text-slate-100 font-sans">
      {/* 1. Persistent Responsive Sidebar */}
      <Sidebar
        activeView={activeView}
        onSelectView={setActiveView}
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
        onDeleteSession={handleDeleteSession}
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={() => setIsSidebarCollapsed((prev) => !prev)}
        isMobileOpen={isMobileSidebarOpen}
        onCloseMobile={() => setIsMobileSidebarOpen(false)}
      />

      {/* 2. Main Content Area */}
      <div className="flex-1 flex flex-col h-full overflow-hidden relative min-w-0">
        {/* Top Header with live ticker marquee & dynamic "Market Dashboard" button */}
        <Header
          indices={dashboardData?.indices}
          activeView={activeView}
          onNavigateDashboard={() => setActiveView('dashboard')}
          clientId={clientId}
          onToggleMobileSidebar={() => setIsMobileSidebarOpen((prev) => !prev)}
        />

        {/* Viewport Content */}
        <main className="flex-1 overflow-y-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-6 relative">
          {activeView === 'dashboard' && (
            <MarketDashboardView
              country={country}
              dashboardData={dashboardData}
              isLoading={isDashboardLoading}
              onRefresh={() => loadDashboard(country)}
              onSelectTicker={handleSelectTicker}
            />
          )}

          {activeView === 'chat' && (
            <FinancialChatView
              messages={messages}
              isStreaming={isStreaming}
              streamingText={streamedText}
              streamingStatus={statusMessage}
              streamingSources={streamingSources}
              streamingError={streamingError}
              onSuggestionClick={handleSuggestedPrompt}
            />
          )}

          {activeView === 'document' && (
            <DocumentAnalyzerView clientId={clientId} />
          )}

          {activeView === 'research' && (
            <DeepResearchView clientId={clientId} />
          )}

          {activeView === 'sentiment' && (
            <RedditSentimentView clientId={clientId} />
          )}

          {activeView === 'stocks' && (
            <StockInspectorView
              initialTicker={inspectedTicker}
              onAskAboutStock={handleSubmitPrompt}
              clientId={clientId}
            />
          )}
        </main>

        {/* 3. Omnibar Docked at the Bottom (with IN/US Country Dropdown) */}
        <div className="sticky bottom-0 left-0 right-0 z-30 pointer-events-auto">
          <Omnibar
            country={country}
            onSelectCountry={handleSelectCountry}
            onSubmitPrompt={handleSubmitPrompt}
            onSelectSuggestion={handleSuggestedPrompt}
            isStreaming={isStreaming}
            onStopStreaming={stopStreaming}
          />
        </div>
      </div>
    </div>
  );
}

export default App;
