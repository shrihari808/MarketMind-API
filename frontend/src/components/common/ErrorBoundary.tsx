import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('[MarketMind UI ErrorBoundary caught an unhandled exception]:', error, errorInfo);
    this.setState({ error, errorInfo });
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    window.location.reload();
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen w-screen bg-[#2a262b] text-slate-100 flex items-center justify-center p-6 font-sans">
          <div className="max-w-md w-full bg-[#221f23] border border-[#3d363f] rounded-2xl p-6 shadow-2xl space-y-5">
            <div className="flex items-center space-x-3 text-rose-400">
              <div className="p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/20">
                <AlertTriangle className="w-6 h-6 text-rose-400" />
              </div>
              <div>
                <h2 className="text-base font-bold text-white tracking-tight">MarketMind Terminal Notice</h2>
                <p className="text-xs text-slate-400">An unexpected rendering issue occurred</p>
              </div>
            </div>

            <div className="bg-[#1d1a1e] rounded-xl p-3 border border-[#3d363f] font-mono text-[11px] text-slate-300 overflow-x-auto max-h-32">
              {this.state.error?.message || 'An unknown runtime error occurred.'}
            </div>

            <p className="text-xs text-slate-400 leading-relaxed">
              Your device session and preferences are intact. You can reload the terminal or reset your session.
            </p>

            <div className="flex items-center space-x-3 pt-2">
              <button
                onClick={this.handleReset}
                className="flex-1 flex items-center justify-center space-x-2 py-2.5 px-4 rounded-xl bg-[#9013fe] hover:bg-[#7c0fd8] text-white font-semibold text-xs transition shadow-md shadow-[#9013fe]/20"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Reload Terminal</span>
              </button>
              <button
                onClick={() => {
                  localStorage.clear();
                  window.location.reload();
                }}
                className="py-2.5 px-4 rounded-xl bg-[#1d1a1e] hover:bg-[#3d363f] text-slate-300 font-medium text-xs border border-[#3d363f] transition"
              >
                Reset Storage
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
