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

  // 3. Market Dashboard State
  const [dashboardData, setDashboardData] = useState<MarketDashboardResponse | null>(null);
  const [isDashboardLoading, setIsDashboardLoading] = useState(false);

  // 4. Chat & Conversation State
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>(() => `session-${Date.now()}`);
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);

  // 5. Stock Inspector target ticker
  const [inspectedTicker, setInspectedTicker] = useState('TATAMOTORS.NS');

  // 6. SSE Streaming Hook for Web RAG
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

  // --- Handle Prompt Submission from Omnibar ---
  // When user types or selects shortcut: Dashboard disappears, switches to chat view
  const handleSubmitPrompt = (promptText: string) => {
    if (!promptText.trim()) return;

    // Transition view from dashboard to chat
    setActiveView('chat');

    // Add user turn to UI immediately
    const userTurn: ChatMessageItem = {
      role: 'user',
      content: promptText,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userTurn]);

    // Dispatch SSE stream to Web RAG endpoint
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
        // Refresh session list to reflect updated session
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
      setMessages(history || []);
    } catch (err) {
      console.error('Failed to load session messages:', err);
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
    <div className="flex h-screen w-screen overflow-hidden bg-[#080C14] text-slate-100 font-sans">
      {/* 1. Persistent Sidebar (Always Present) */}
      <Sidebar
        activeView={activeView}
        onSelectView={setActiveView}
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
        onDeleteSession={handleDeleteSession}
      />

      {/* 2. Main Content Area */}
      <div className="flex-1 flex flex-col h-full overflow-hidden relative">
        {/* Top Header with live ticker marquee & dynamic "Market Dashboard" button */}
        <Header
          indices={dashboardData?.indices}
          activeView={activeView}
          onNavigateDashboard={() => setActiveView('dashboard')}
          clientId={clientId}
        />

        {/* Viewport Content */}
        <main className="flex-1 overflow-y-auto px-4 sm:px-6 lg:px-8 py-6 relative">
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
              onSuggestionClick={handleSubmitPrompt}
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
        <div className="absolute bottom-0 left-0 right-0 z-30 pointer-events-auto">
          <Omnibar
            country={country}
            onSelectCountry={handleSelectCountry}
            onSubmitPrompt={handleSubmitPrompt}
            isStreaming={isStreaming}
            onStopStreaming={stopStreaming}
          />
        </div>
      </div>
    </div>
  );
}

export default App;
