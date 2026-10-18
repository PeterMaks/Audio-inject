import React, { useEffect, useState } from "react";
import { Disc, Minus, Square, X } from "lucide-react";
import {
  checkSystemHealth,
  closeWindow,
  maximizeWindow,
  minimizeWindow,
} from "../lib/tauriClient";
import { HealthStatus } from "../types/injector";

export const Titlebar: React.FC = () => {
  const [health, setHealth] = useState<HealthStatus | null>(null);

  useEffect(() => {
    checkSystemHealth()
      .then(setHealth)
      .catch((err) => console.error("Health check error:", err));
  }, []);

  return (
    <header
      data-tauri-drag-region
      className="h-11 w-full flex items-center justify-between px-4 select-none z-50 border-b border-white/[0.07] bg-[#141419]/70 backdrop-blur-2xl shrink-0"
    >
      {/* Left: App Identity */}
      <div className="flex items-center space-x-2.5 pointer-events-none">
        <div className="flex items-center justify-center w-6 h-6 rounded-lg bg-gradient-to-b from-[#0A84FF] to-[#0055D4] shadow-sm border border-white/20">
          <Disc className="w-3.5 h-3.5 text-white" />
        </div>
        <span className="text-[13px] font-semibold tracking-tight text-white/90">
          FLAC Meta Injector
        </span>
        <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-white/[0.06] text-white/55 border border-white/[0.08]">
          Studio
        </span>
      </div>

      {/* Center: Subtle Apple Hardware/Binary Health Indicators */}
      <div className="hidden md:flex items-center space-x-2 pointer-events-auto">
        <div
          title={`Python ${health?.python_version || "3.11+"} (${health?.in_venv ? "Virtual Env" : "System"
            })`}
          className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-white/[0.04] border border-white/[0.07] text-[11px] text-white/70 tabular-nums"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-[#30D158]" />
          <span>Python {health?.python_version?.split(" ")[0] || "3.13"}</span>
        </div>

        <div
          title={health?.ffmpeg.path || "FFmpeg binary status"}
          className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-white/[0.04] border border-white/[0.07] text-[11px] text-white/70"
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${health?.ffmpeg.available ? "bg-[#30D158]" : "bg-[#FF453A]"
              }`}
          />
          <span>FFmpeg</span>
        </div>

        <div
          title={health?.fpcalc.path || "Chromaprint fpcalc binary status"}
          className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-white/[0.04] border border-white/[0.07] text-[11px] text-white/70"
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${health?.fpcalc.available ? "bg-[#30D158]" : "bg-[#FF9F0A]"
              }`}
          />
          <span>Chromaprint</span>
        </div>
      </div>

      {/* Right: Frameless Window Controls */}
      <div className="flex items-center space-x-1 pointer-events-auto">
        <button
          onClick={minimizeWindow}
          className="w-8 h-7 flex items-center justify-center rounded-md text-white/50 hover:text-white hover:bg-white/[0.08] transition-colors"
          title="Minimize"
        >
          <Minus className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={maximizeWindow}
          className="w-8 h-7 flex items-center justify-center rounded-md text-white/50 hover:text-white hover:bg-white/[0.08] transition-colors"
          title="Maximize"
        >
          <Square className="w-3 h-3" />
        </button>
        <button
          onClick={closeWindow}
          className="w-8 h-7 flex items-center justify-center rounded-md text-white/50 hover:text-white hover:bg-[#FF453A] transition-colors"
          title="Close"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </header>
  );
};