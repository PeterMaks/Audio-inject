import React, { useState } from "react";
import {
  Sparkles,
  Cpu,
  Database,
  Music2,
  Sliders,
  CheckCircle2,
  Clock,
  Disc,
} from "lucide-react";
import { InjectItemResult, ProgressEvent, ScanItem } from "../types/injector";

interface InjectViewProps {
  items: ScanItem[];
  isInjecting: boolean;
  currentProgress: ProgressEvent | null;
  lastResults: InjectItemResult[];
  onStartInject: (params: {
    paths: string[];
    threshold: number;
    dryRun: boolean;
    overwrite: boolean;
    convertWav: boolean;
  }) => void;
}

const AppleToggle: React.FC<{
  checked: boolean;
  onChange: (val: boolean) => void;
  label: string;
  description: string;
}> = ({ checked, onChange, label, description }) => (
  <div
    onClick={() => onChange(!checked)}
    className="flex items-center justify-between py-2.5 cursor-pointer group"
  >
    <div className="pr-4">
      <div className="text-xs font-medium text-white group-hover:text-white/95">
        {label}
      </div>
      <div className="text-[11px] text-white/45">{description}</div>
    </div>
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      className={`w-10 h-6 rounded-full p-0.5 transition-colors duration-200 shrink-0 ${checked ? "bg-[#30D158]" : "bg-white/[0.14]"
        }`}
    >
      <div
        className={`w-5 h-5 rounded-full bg-white shadow-md transform transition-transform duration-200 ${checked ? "translate-x-4" : "translate-x-0"
          }`}
      />
    </button>
  </div>
);

export const InjectView: React.FC<InjectViewProps> = ({
  items,
  isInjecting,
  currentProgress,
  lastResults,
  onStartInject,
}) => {
  const [threshold, setThreshold] = useState<number>(0.7);
  const [dryRun, setDryRun] = useState<boolean>(false);
  const [overwrite, setOverwrite] = useState<boolean>(false);
  const [convertWav, setConvertWav] = useState<boolean>(true);
  const [onlyIncomplete, setOnlyIncomplete] = useState<boolean>(true);

  const getStageNodeIndex = (stage?: string): number => {
    if (!stage) return -1;
    switch (stage) {
      case "fingerprint":
        return 0;
      case "acoustid":
      case "musicbrainz":
        return 1;
      case "itunes":
      case "art":
      case "cover_art":
        return 2;
      case "deezer":
        return 3;
      case "spotify":
      case "songlink":
        return 4;
      case "merge":
      case "write":
      case "done":
      case "finished":
        return 5;
      default:
        return 0;
    }
  };

  const activeNodeIndex = getStageNodeIndex(currentProgress?.stage);

  const pipelineNodes = [
    { title: "Chromaprint", sub: "Acoustic ID", icon: Cpu },
    { title: "MusicBrainz", sub: "ISRC & MBID", icon: Database },
    { title: "Apple Music", sub: "3000px Master", icon: Music2 },
    { title: "Deezer", sub: "BPM & Advisory", icon: Sliders },
    { title: "Spotify", sub: "Canonical Genres", icon: Disc },
  ];

  const targetItems = onlyIncomplete
    ? items.filter((i) => i.is_incomplete)
    : items;

  const handleExecute = () => {
    onStartInject({
      paths: targetItems.map((i) => i.path),
      threshold,
      dryRun,
      overwrite,
      convertWav,
    });
  };

  return (
    <div className="flex flex-col h-full space-y-5 overflow-y-auto pr-1">
      {/* Apple Continuity-Style 5-Node Signal Chain */}
      <div className="p-5 rounded-2xl glass-panel space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-white/90">
            Resolution Waterfall Signal Chain
          </span>
          <span className="text-[11px] font-medium px-2.5 py-0.5 rounded-full bg-white/[0.06] text-white/70 border border-white/[0.08]">
            {isInjecting
              ? `Active: ${currentProgress?.stage || "Resolving"}`
              : "Ready"}
          </span>
        </div>

        <div className="grid grid-cols-5 gap-3">
          {pipelineNodes.map((node, idx) => {
            const Icon = node.icon;
            const isCompleted = isInjecting && activeNodeIndex > idx;
            const isActive = isInjecting && activeNodeIndex === idx;

            return (
              <div
                key={node.title}
                className={`p-3.5 rounded-2xl border transition-all duration-300 flex flex-col items-center text-center ${isActive
                    ? "bg-[#0A84FF]/15 border-[#0A84FF] node-active-pulse"
                    : isCompleted
                      ? "bg-[#30D158]/10 border-[#30D158]/30"
                      : "bg-white/[0.03] border-white/[0.07]"
                  }`}
              >
                <div
                  className={`w-9 h-9 rounded-xl flex items-center justify-center mb-2 ${isActive
                      ? "bg-[#0A84FF] text-white shadow-md"
                      : isCompleted
                        ? "bg-[#30D158]/20 text-[#30D158]"
                        : "bg-white/[0.06] text-white/60"
                    }`}
                >
                  <Icon className="w-4 h-4" />
                </div>
                <div className="text-xs font-semibold text-white">
                  {node.title}
                </div>
                <div className="text-[11px] text-white/45 mt-0.5">
                  {node.sub}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Two-Column Apple Settings Group */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Confidence Slider Card */}
        <div className="p-5 rounded-2xl glass-panel flex flex-col justify-between space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs font-semibold text-white">
                Match Confidence Threshold
              </div>
              <div className="text-[11px] text-white/45 mt-0.5">
                Minimum RapidFuzz & duration similarity required to auto-write
              </div>
            </div>
            <span className="text-sm font-semibold tabular-nums text-[#0A84FF] bg-[#0A84FF]/15 px-2.5 py-1 rounded-lg border border-[#0A84FF]/30">
              {(threshold * 100).toFixed(0)}%
            </span>
          </div>

          <div className="space-y-2">
            <input
              type="range"
              min="0.40"
              max="0.95"
              step="0.05"
              value={threshold}
              onChange={(e) => setThreshold(parseFloat(e.target.value))}
              className="w-full apple-slider"
            />
            <div className="flex justify-between text-[11px] text-white/40 tabular-nums">
              <span>40% (Permissive)</span>
              <span className="text-white/70 font-medium">70% (Recommended)</span>
              <span>95% (Strict)</span>
            </div>
          </div>
        </div>

        {/* Apple Capsule Switches Card */}
        <div className="p-5 rounded-2xl glass-panel divide-y divide-white/[0.06]">
          <AppleToggle
            checked={onlyIncomplete}
            onChange={setOnlyIncomplete}
            label="Incomplete Tracks Only"
            description="Skip tracks already fully tagged with verified 3000px cover art"
          />
          <AppleToggle
            checked={dryRun}
            onChange={setDryRun}
            label="Dry-Run Simulation"
            description="Preview resolved tags without modifying files on disk"
          />
          <AppleToggle
            checked={overwrite}
            onChange={setOverwrite}
            label="Overwrite Existing Metadata"
            description="Replace populated Vorbis/ID3 tags with fresh canonical values"
          />
          <AppleToggle
            checked={convertWav}
            onChange={setConvertWav}
            label="Auto-Encode WAV Masters"
            description="Convert uncompressed WAV tracks to FLAC before tagging"
          />
        </div>
      </div>

      {/* Live Progress Bar */}
      {isInjecting && (
        <div className="p-4 rounded-2xl glass-panel space-y-2.5 border border-[#0A84FF]/40">
          <div className="flex justify-between text-xs tabular-nums">
            <span className="text-white/90 font-medium truncate max-w-lg">
              {currentProgress?.message || "Resolving metadata across providers…"}
            </span>
            <span className="text-[#0A84FF] font-semibold">
              {currentProgress?.percent?.toFixed(0) || 0}%
            </span>
          </div>
          <div className="w-full h-1.5 rounded-full bg-white/[0.08] overflow-hidden">
            <div
              className="h-full bg-[#0A84FF] transition-all duration-300 rounded-full"
              style={{ width: `${currentProgress?.percent || 0}%` }}
            />
          </div>
        </div>
      )}

      {/* Execution Bar */}
      <div className="flex items-center justify-between p-4 rounded-2xl glass-panel">
        <div className="text-xs text-white/60 tabular-nums">
          Ready to process{" "}
          <span className="text-white font-semibold">{targetItems.length}</span> of{" "}
          <span className="text-white/80">{items.length}</span> audio track(s)
        </div>

        <button
          onClick={handleExecute}
          disabled={isInjecting || targetItems.length === 0}
          className="apple-btn-primary flex items-center space-x-2 px-6 py-2.5 rounded-xl text-white text-xs font-semibold disabled:opacity-40"
        >
          <Sparkles className="w-4 h-4" />
          <span>
            {isInjecting
              ? "Running Waterfall…"
              : dryRun
                ? `Simulate Injection (${targetItems.length})`
                : `Inject Metadata (${targetItems.length})`}
          </span>
        </button>
      </div>

      {/* Results History */}
      {lastResults.length > 0 && (
        <div className="space-y-2.5">
          <h4 className="text-xs font-semibold text-white/70 px-1 tabular-nums">
            Verification Log ({lastResults.length})
          </h4>
          <div className="space-y-2">
            {lastResults.map((res, i) => (
              <div
                key={i}
                className="p-3.5 rounded-2xl glass-panel flex items-center justify-between text-xs"
              >
                <div className="flex items-center space-x-3 min-w-0">
                  {res.status === "injected" ? (
                    <CheckCircle2 className="w-4 h-4 text-[#30D158] shrink-0" />
                  ) : (
                    <Clock className="w-4 h-4 text-[#0A84FF] shrink-0" />
                  )}
                  <div className="truncate">
                    <div className="font-medium text-white truncate">
                      {res.metadata
                        ? `${res.metadata.artist} — ${res.metadata.title}`
                        : res.file}
                    </div>
                    <div className="text-[11px] text-white/45 truncate">
                      {res.metadata?.album || res.reason || res.error || "Verified"}
                    </div>
                  </div>
                </div>

                <div className="flex items-center space-x-2.5 shrink-0 tabular-nums">
                  {res.confidence_score !== undefined && (
                    <span className="px-2 py-0.5 rounded-md bg-white/[0.06] text-white/80 text-[11px]">
                      {(res.confidence_score * 100).toFixed(0)}% match
                    </span>
                  )}
                  <span
                    className={`px-2.5 py-0.5 rounded-full font-medium text-[11px] capitalize ${res.status === "injected"
                        ? "bg-[#30D158]/20 text-[#30D158]"
                        : "bg-white/[0.08] text-white/70"
                      }`}
                  >
                    {res.status.replace("_", " ")}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};