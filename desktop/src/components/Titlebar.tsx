import React, { useEffect, useState } from "react";
import { Disc, Minus, Square, X, RefreshCw } from "lucide-react";
import {
  checkSystemHealth,
  closeWindow,
  maximizeWindow,
  minimizeWindow,
} from "../lib/tauriClient";
import { HealthStatus } from "../types/injector";

export const Titlebar: React.FC = React.memo(function Titlebar() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchHealth = async () => {
    setRefreshing(true);
    try {
      const status = await checkSystemHealth();
      setHealth(status);
    } catch (err) {
      console.error("Health check error:", err);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  return (
    <header
      data-tauri-drag-region
      className="h-10 w-full flex items-center justify-between px-3 select-none z-50 border-b border-white/[0.08] bg-[#181818] shrink-0"
    >
      {/* Left: App Identity */}
      <div className="flex items-center space-x-2 pointer-events-none">
        <div className="flex items-center justify-center w-5 h-5 rounded-md bg-[#0A84FF] shadow-sm">
          <Disc className="w-3.5 h-3.5 text-white" />
        </div>
        <span className="text-xs font-semibold tracking-tight text-[#F5F5F7]">
          FLAC Meta Injector
        </span>
        <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-white/[0.06] text-[#A1A1A6] border border-white/[0.08]">
          Studio
        </span>
      </div>

      {/* Center: Binary & API Readiness Indicators */}
      <div className="hidden md:flex items-center space-x-1.5 pointer-events-auto">
        <div
          title={`Python ${health?.python_version || "3.11+"} (${
            health?.in_venv ? "Virtual Env" : "System"
          })`}
          className="flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full bg-white/[0.04] border border-white/[0.07] text-xs text-[#F5F5F7]/85 tabular-nums"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-[#34C759]" />
          <span>Python {health?.python_version?.split(" ")[0] || "3.13"}</span>
        </div>

        <div
          title={health?.ffmpeg.path || "FFmpeg binary status"}
          className="flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full bg-white/[0.04] border border-white/[0.07] text-xs text-[#F5F5F7]/85"
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              health?.ffmpeg.available ? "bg-[#34C759]" : "bg-[#FF453A]"
            }`}
          />
          <span>FFmpeg</span>
        </div>

        <div
          title={health?.fpcalc.path || "Chromaprint fpcalc binary status"}
          className="flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full bg-white/[0.04] border border-white/[0.07] text-xs text-[#F5F5F7]/85"
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              health?.fpcalc.available ? "bg-[#34C759]" : "bg-[#FF9F0A]"
            }`}
          />
          <span>Chromaprint</span>
        </div>

        <div
          title={
            health?.env_status.acoustid_configured
              ? "AcoustID API Key configured"
              : "AcoustID API Key missing — configure in Settings"
          }
          className="flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full bg-white/[0.04] border border-white/[0.07] text-xs text-[#F5F5F7]/85"
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              health?.env_status.acoustid_configured
                ? "bg-[#34C759]"
                : "bg-[#FF9F0A]"
            }`}
          />
          <span>AcoustID</span>
        </div>

        <button
          type="button"
          onClick={fetchHealth}
          title="Refresh system status"
          className="p-1 rounded-md text-[#A1A1A6] hover:text-[#F5F5F7] hover:bg-white/[0.06] transition-colors"
        >
          <RefreshCw
            className={`w-3 h-3 ${refreshing ? "animate-spin text-[#0A84FF]" : ""}`}
          />
        </button>
      </div>

      {/* Right: Window Controls */}
      <div className="flex items-center space-x-1 pointer-events-auto">
        <button
          type="button"
          onClick={minimizeWindow}
          className="w-7 h-6 flex items-center justify-center rounded-md text-[#A1A1A6] hover:text-[#F5F5F7] hover:bg-white/[0.08] transition-colors"
          title="Minimize"
        >
          <Minus className="w-3.5 h-3.5" />
        </button>
        <button
          type="button"
          onClick={maximizeWindow}
          className="w-7 h-6 flex items-center justify-center rounded-md text-[#A1A1A6] hover:text-[#F5F5F7] hover:bg-white/[0.08] transition-colors"
          title="Maximize"
        >
          <Square className="w-3 h-3" />
        </button>
        <button
          type="button"
          onClick={closeWindow}
          className="w-7 h-6 flex items-center justify-center rounded-md text-[#A1A1A6] hover:text-white hover:bg-[#FF453A] transition-colors"
          title="Close"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </header>
  );
});
