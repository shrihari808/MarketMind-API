import React, { useState, useEffect } from 'react';
import { Zap, CheckCircle2, Clock, X, RefreshCw } from 'lucide-react';

interface ColdStartNotificationProps {
  isColdStarting: boolean;
  elapsedSeconds: number;
  isBackendConnected: boolean;
  hasCachedData: boolean;
  onDismiss?: () => void;
}

export const ColdStartNotification: React.FC<ColdStartNotificationProps> = ({
  isColdStarting,
  elapsedSeconds,
  isBackendConnected,
  hasCachedData,
  onDismiss,
}) => {
  const [isDismissed, setIsDismissed] = useState(false);
  const [showSuccessToast, setShowSuccessToast] = useState(false);

  // Trigger brief success banner when transitioning from cold start to connected
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    let raf: number | undefined;
    if (isBackendConnected && elapsedSeconds > 0) {
      raf = requestAnimationFrame(() => {
        setShowSuccessToast(true);
      });
      timer = setTimeout(() => {
        setShowSuccessToast(false);
      }, 3000);
    }
    return () => {
      if (raf) cancelAnimationFrame(raf);
      if (timer) clearTimeout(timer);
    };
  }, [isBackendConnected, elapsedSeconds]);

  if (isDismissed) return null;

  // 1. Success state banner (fades after 3s)
  if (showSuccessToast) {
    return (
      <aside
        aria-label="Server status alert"
        className="w-full bg-[#16291e] border-b border-emerald-500/30 text-emerald-300 px-4 py-2.5 transition-all duration-300 shadow-md"
      >
        <div className="max-w-7xl mx-auto flex items-center justify-between text-xs sm:text-sm">
          <div className="flex items-center space-x-2.5 font-medium">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>Institutional Engine Online • Live market data and AI pipelines active.</span>
          </div>
          <span className="font-mono text-[11px] text-emerald-400/80 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-500/20">
            Woke in {elapsedSeconds}s
          </span>
        </div>
      </aside>
    );
  }

  // 2. Cold Start Active Banner
  if (isColdStarting) {
    // Estimated time is ~45s. Calculate approximate percentage for visual indicator.
    const progressPercent = Math.min(95, Math.round((elapsedSeconds / 45) * 100));

    return (
      <aside
        aria-label="Server status alert"
        className="w-full bg-[#241c16] border-b border-amber-500/30 text-slate-200 px-4 py-3 transition-all duration-300 shadow-lg relative overflow-hidden"
      >
        {/* Animated micro progress line at the bottom of the banner */}
        <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#3d2e20]">
          <div
            className="h-full bg-linear-to-r from-amber-500 to-[#c084fc] transition-all duration-1000 ease-out"
            style={{ width: `${progressPercent}%` }}
          />
        </div>

        <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center justify-between gap-2.5">
          <div className="flex items-start sm:items-center space-x-3">
            <div className="p-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 shrink-0 mt-0.5 sm:mt-0">
              <Zap className="w-4 h-4 animate-pulse" />
            </div>

            <div>
              <div className="flex items-center space-x-2">
                <span className="font-semibold text-xs sm:text-sm text-amber-300">
                  Cloud Backend Waking Up (Cold Start)
                </span>
                <span className="hidden sm:inline-flex items-center px-1.5 py-0.2 rounded text-[10px] font-mono bg-amber-500/20 text-amber-300 border border-amber-500/30">
                  Render Free Tier
                </span>
              </div>
              <p className="text-[11px] sm:text-xs text-slate-400 mt-0.5 leading-relaxed">
                {hasCachedData
                  ? 'Showing cached terminal snapshot while the backend container and database pool boot (~35–50s).'
                  : 'Backend container is booting from idle sleep (~35–50s). Live data will connect automatically.'}
              </p>
            </div>
          </div>

          <div className="flex items-center justify-between sm:justify-end space-x-3 text-xs shrink-0 pl-7 sm:pl-0">
            <div className="flex items-center space-x-1.5 font-mono text-amber-300/90 bg-[#1d1612] px-2.5 py-1 rounded-md border border-amber-500/20">
              <Clock className="w-3.5 h-3.5 text-amber-400" />
              <span>Elapsed: {elapsedSeconds}s</span>
              <span className="text-slate-500 text-[10px] hidden sm:inline">(est. ~45s)</span>
            </div>

            <div className="flex items-center space-x-1">
              <RefreshCw className="w-3 h-3 text-amber-400 animate-spin" />
              <span className="text-[11px] text-amber-400/90 font-medium">Reconnecting</span>
            </div>

            {onDismiss && (
              <button
                type="button"
                onClick={() => {
                  setIsDismissed(true);
                  onDismiss();
                }}
                className="p-1 text-slate-400 hover:text-white rounded hover:bg-white/5 transition"
                title="Dismiss banner"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>
      </aside>
    );
  }

  return null;
};
