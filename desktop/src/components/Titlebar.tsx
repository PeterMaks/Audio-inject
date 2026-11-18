import React, { useEffect, useState } from "react";
import { Disc, RefreshCw, X, Minus, Plus } from "lucide-react";
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
      className="h-10 w-full flex items-center justify-between px-3.5 select-none z-50 border-b border-white/[0.08] bg-[#18181A]/85 backdrop-blur-xl shrink-0"
    >
      {/* Left: macOS Traffic Lights + App Brand */}
      <div className="flex items-center space-x-4">
        {/* macOS Traffic Light Buttons */}
        <div className="group flex items-center space-x-2 pointer-events-auto">
          <button
            type="button"
            onClick={closeWindow}
            title="Close"
            className="w-3 h-3 rounded-full traffic-light-close flex items-center justify-center transition-transform active:scale-90 focus:outline-none"
          >
            <X className="w-2 h-2 text-black/70 opacity-0 group-hover:opacity-100 transition-opacity stroke-[2.5]" />
          </button>
          <button
            type="button"
            onClick={minimizeWindow}
            title="Minimize"
            className="w-3 h-3 rounded-full traffic-light-minimize flex items-center justify-center transition-transform active:scale-90 focus:outline-none"
          >
            <Minus className="w-2 h-2 text-black/70 opacity-0 group-hover:opacity-100 transition-opacity stroke-[2.5]" />
          </button>
          <button
            type="button"
            onClick={maximizeWindow}
            title="Zoom / Maximize"
            className="w-3 h-3 rounded-full traffic-light-maximize flex items-center justify-center transition-transform active:scale-90 focus:outline-none"
          >
            <Plus className="w-2 h-2 text-black/70 opacity-0 group-hover:opacity-100 transition-opacity stroke-[2.5]" />
          </button>
        </div>

        {/* App Title & Identity */}
        <div className="flex items-center space-x-2 pointer-events-none">
          <div className="flex items-center justify-center w-5 h-5 rounded-md bg-[#007AFF] shadow-sm">
            <Disc className="w-3.5 h-3.5 text-white" />
          </div>
          <span className="text-xs font-semibold tracking-tight text-[#FFFFFF]">
            FLAC Meta Injector
          </span>
          <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-white/[0.06] text-[#8E8E93] border border-white/[0.08]">
            Studio
          </span>
        </div>
      </div>

      {/* Right: macOS Status Capsules & Refresh Action */}
      <div className="flex items-center space-x-1.5 pointer-events-auto">
        <div
          title={`Python ${health?.python_version || "3.11+"} (${
            health?.in_venv ? "Virtual Env" : "System"
          })`}
          className="flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full bg-white/[0.04] border border-white/[0.07] text-[11px] text-[#F5F5F7]/90 tabular-nums"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-[#34C759]" />
          <span>Python {health?.python_version?.split(" ")[0] || "3.13"}</span>
        </div>

        <div
          title={health?.ffmpeg.path || "FFmpeg binary status"}
          className="flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full bg-white/[0.04] border border-white/[0.07] text-[11px] text-[#F5F5F7]/90"
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              health?.ffmpeg.available ? "bg-[#34C759]" : "bg-[#FF3B30]"
            }`}
          />
          <span>FFmpeg</span>
        </div>

        <div
          title={health?.fpcalc.path || "Chromaprint fpcalc binary status"}
          className="flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full bg-white/[0.04] border border-white/[0.07] text-[11px] text-[#F5F5F7]/90"
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              health?.fpcalc.available ? "bg-[#34C759]" : "bg-[#FF9500]"
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
          className="flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full bg-white/[0.04] border border-white/[0.07] text-[11px] text-[#F5F5F7]/90"
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              health?.env_status.acoustid_configured
                ? "bg-[#34C759]"
                : "bg-[#FF9500]"
            }`}
          />
          <span>AcoustID</span>
        </div>

        <button
          type="button"
          onClick={fetchHealth}
          title="Refresh system status"
          className="p-1 rounded-md text-[#8E8E93] hover:text-[#FFFFFF] hover:bg-white/[0.08] transition-colors"
        >
          <RefreshCw
            className={`w-3 h-3 ${refreshing ? "animate-spin text-[#007AFF]" : ""}`}
          />
        </button>
      </div>
    </header>
  );
});
