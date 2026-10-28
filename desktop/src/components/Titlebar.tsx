import React, { useEffect, useState } from "react";
import { Disc, Minus, Square, X, RefreshCw } from "lucide-react";
import {
  checkSystemHealth,
  closeWindow,
  maximizeWindow,
  minimizeWindow,
} from "../lib/tauriClient";
import { HealthStatus } from "../types/injector";

export const Titlebar: React.FC = () => {
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
      className="h-11 w-full flex items-center justify-between px-4 select-none z-50 border-b border-white/[0.08] bg-[#141416]/80 backdrop-blur-xl shrink-0"
    >
      {/* Left: App Identity */}
      <div className="flex items-center space-x-2.5 pointer-events-none">
        <div className="flex items-center justify-center w-6 h-6 rounded-[7px] bg-gradient-to-b from-[#0A84FF] to-[#0055D4] shadow-sm border border-white/20">
          <Disc className="w-3.5 h-3.5 text-white" />
        </div>
        <span className="text-[13px] font-semibold tracking-tight text-[#F5F5F7]">
          FLAC Meta Injector
        </span>
        <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-white/[0.06] text-[#86868B] border border-white/[0.08]">
          Studio
        </span>
      </div>

      {/* Center: Hardware, Binary & API Readiness Indicators */}
      <div className="hidden md:flex items-center space-x-1.5 pointer-events-auto">
        <div
          title={`Python ${health?.python_version || "3.11+"} (${
            health?.in_venv ? "Virtual Env" : "System"
          })`}
          className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-white/[0.04] border border-white/[0.07] text-[11px] text-[#F5F5F7]/80 tabular-nums"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-[#34C759]" />
          <span>Python {health?.python_version?.split(" ")[0] || "3.13"}</span>
        </div>

        <div
          title={health?.ffmpeg.path || "FFmpeg binary status"}
          className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-white/[0.04] border border-white/[0.07] text-[11px] text-[#F5F5F7]/80"
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
          className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-white/[0.04] border border-white/[0.07] text-[11px] text-[#F5F5F7]/80"
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
              ? "AcoustID API Key Configured"
              : "AcoustID API Key Missing — Configure in Settings"
          }
          className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-white/[0.04] border border-white/[0.07] text-[11px] text-[#F5F5F7]/80"
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
          onClick={fetchHealth}
          title="Refresh binary & API health status"
          className="p-1.5 rounded-full text-[#86868B] hover:text-[#F5F5F7] hover:bg-white/[0.06] active:scale-[0.95] transition-all"
        >
          <RefreshCw
            className={`w-3 h-3 ${refreshing ? "animate-spin text-[#0A84FF]" : ""}`}
          />
        </button>
      </div>

      {/* Right: Frameless Window Controls */}
      <div className="flex items-center space-x-1 pointer-events-auto">
        <button
          onClick={minimizeWindow}
          className="w-8 h-7 flex items-center justify-center rounded-md text-[#86868B] hover:text-[#F5F5F7] hover:bg-white/[0.08] active:scale-[0.95] transition-all"
          title="Minimize"
        >
          <Minus className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={maximizeWindow}
          className="w-8 h-7 flex items-center justify-center rounded-md text-[#86868B] hover:text-[#F5F5F7] hover:bg-white/[0.08] active:scale-[0.95] transition-all"
          title="Maximize"
        >
          <Square className="w-3 h-3" />
        </button>
        <button
          onClick={closeWindow}
          className="w-8 h-7 flex items-center justify-center rounded-md text-[#86868B] hover:text-white hover:bg-[#FF453A] active:scale-[0.95] transition-all"
          title="Close"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </header>
  );
};