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
  Share2,
  ChevronDown,
  ChevronUp,
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
      <div className="text-xs font-medium text-[#F5F5F7] group-hover:text-white">
        {label}
      </div>
      <div className="text-[11px] text-[#86868B]">{description}</div>
    </div>
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      className={`w-10 h-6 rounded-full p-0.5 transition-colors duration-200 shrink-0 ${
        checked ? "bg-[#34C759]" : "bg-white/[0.14]"
      }`}
    >
      <div
        className={`w-5 h-5 rounded-full bg-white shadow-md transform transition-transform duration-200 ${
          checked ? "translate-x-4" : "translate-x-0"
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
  const [expandedRow, setExpandedRow] = useState<number | null>(null);

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
        return 4;
      case "songlink":
      case "merge":
      case "write":
        return 5;
      case "done":
      case "finished":
        return 6;
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
    { title: "Spotify", sub: "Genres & Release", icon: Disc },
    { title: "Songlink", sub: "Cross-Platform", icon: Share2 },
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
    <div className="flex flex-col h-full space-y-4 overflow-y-auto pr-1">
      {/* 6-Node Continuity Signal Chain (Concentric: Outer 20px p-4, Inner 12px) */}
      <div className="p-4 rounded-[20px] glass-panel space-y-3.5">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-[#F5F5F7]">
            Resolution Waterfall Signal Chain
          </span>
          <span className="text-[11px] font-medium px-2.5 py-0.5 rounded-full bg-white/[0.06] text-[#86868B] border border-white/[0.08] tabular-nums">
            {isInjecting
              ? `Active Stage: ${currentProgress?.stage || "Resolving"}`
              : "Idle • 6 Providers Armed"}
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5">
          {pipelineNodes.map((node, idx) => {
            const Icon = node.icon;
            const isCompleted = isInjecting && activeNodeIndex > idx;
            const isActive = isInjecting && activeNodeIndex === idx;

            return (
              <div
                key={node.title}
                className={`p-3 rounded-[12px] border transition-all duration-200 flex flex-col items-center text-center ${
                  isActive
                    ? "bg-[#0A84FF]/15 border-[#0A84FF]"
                    : isCompleted
                      ? "bg-[#34C759]/10 border-[#34C759]/35"
                      : "surface-elevated"
                }`}
              >
                <div
                  className={`w-8 h-8 rounded-[9px] flex items-center justify-center mb-1.5 ${
                    isActive
                      ? "bg-[#0A84FF] text-white shadow-sm"
                      : isCompleted
                        ? "bg-[#34C759]/20 text-[#34C759]"
                        : "bg-white/[0.06] text-[#86868B]"
                  }`}
                >
                  <Icon className="w-4 h-4" />
                </div>
                <div className="text-xs font-semibold text-[#F5F5F7]">
                  {node.title}
                </div>
                <div className="text-[10px] text-[#86868B] mt-0.5">
                  {node.sub}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Two-Column Apple Settings Bento */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Confidence Slider Card */}
        <div className="p-5 rounded-[20px] glass-panel flex flex-col justify-between space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs font-semibold text-[#F5F5F7]">
                Match Confidence Threshold
              </div>
              <div className="text-[11px] text-[#86868B] mt-0.5">
                Minimum RapidFuzz & duration similarity required to auto-write
              </div>
            </div>
            <span className="text-sm font-semibold tabular-nums text-[#0A84FF] bg-[#0A84FF]/15 px-2.5 py-1 rounded-[10px] border border-[#0A84FF]/30">
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
            <div className="flex justify-between text-[11px] text-[#86868B] tabular-nums">
              <span>40% (Permissive)</span>
              <span className="text-[#F5F5F7]/80 font-medium">
                70% (Recommended)
              </span>
              <span>95% (Strict)</span>
            </div>
          </div>
        </div>

        {/* Apple Capsule Switches Card */}
        <div className="p-5 rounded-[20px] glass-panel divide-y divide-white/[0.06]">
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
            description="Preview resolved Vorbis/ID3 tags without modifying files on disk"
          />
          <AppleToggle
            checked={overwrite}
            onChange={setOverwrite}
            label="Overwrite Existing Metadata"
            description="Replace populated tags with fresh canonical provider values"
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
        <div className="p-4 rounded-[20px] glass-panel space-y-2.5 border border-[#0A84FF]/40">
          <div className="flex justify-between text-xs tabular-nums">
            <span className="text-[#F5F5F7] font-medium truncate max-w-lg">
              {currentProgress?.message ||
                "Resolving metadata across providers…"}
            </span>
            <span className="text-[#0A84FF] font-semibold">
              {currentProgress?.percent?.toFixed(0) || 0}%
            </span>
          </div>
          <div className="w-full h-1.5 rounded-full bg-white/[0.08] overflow-hidden">
            <div
              className="h-full bg-[#0A84FF] transition-all duration-200 rounded-full"
              style={{ width: `${currentProgress?.percent || 0}%` }}
            />
          </div>
        </div>
      )}

      {/* Execution Bar */}
      <div className="flex items-center justify-between p-4 rounded-[20px] glass-panel">
        <div className="text-xs text-[#86868B] tabular-nums">
          Ready to process{" "}
          <span className="text-[#F5F5F7] font-semibold">
            {targetItems.length}
          </span>{" "}
          of <span className="text-[#F5F5F7]/85">{items.length}</span> audio
          track(s)
        </div>

        <button
          onClick={handleExecute}
          disabled={isInjecting || targetItems.length === 0}
          className="apple-btn-primary flex items-center space-x-2 px-6 py-2.5 rounded-[12px] text-white text-xs font-semibold disabled:opacity-40"
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

      {/* Rich Verification & Dry-Run Diff Log */}
      {lastResults.length > 0 && (
        <div className="space-y-2.5">
          <h4 className="text-xs font-semibold text-[#86868B] px-1 tabular-nums">
            Verification Log ({lastResults.length})
          </h4>
          <div className="space-y-2">
            {lastResults.map((res, i) => {
              const meta = res.metadata;
              const isExpanded = expandedRow === i;

              return (
                <div
                  key={i}
                  className="p-3.5 rounded-[16px] glass-panel space-y-2.5 text-xs"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3 min-w-0">
                      {res.status === "injected" ? (
                        <CheckCircle2 className="w-4 h-4 text-[#34C759] shrink-0" />
                      ) : (
                        <Clock className="w-4 h-4 text-[#0A84FF] shrink-0" />
                      )}
                      <div className="truncate">
                        <div className="font-medium text-[#F5F5F7] truncate">
                          {meta ? `${meta.artist} — ${meta.title}` : res.file}
                        </div>
                        <div className="text-[11px] text-[#86868B] truncate tabular-nums">
                          {meta?.album ||
                            res.reason ||
                            res.error ||
                            "Verified"}
                          {meta?.isrc ? ` • ISRC: ${meta.isrc}` : ""}
                          {meta?.bpm ? ` • ${meta.bpm} BPM` : ""}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center space-x-2 shrink-0 tabular-nums">
                      {meta?.source_provider && (
                        <span className="px-2 py-0.5 rounded-[6px] bg-white/[0.06] text-[#86868B] text-[10px] uppercase font-semibold">
                          {meta.source_provider}
                        </span>
                      )}
                      {res.confidence_score !== undefined && (
                        <span className="px-2 py-0.5 rounded-[6px] bg-white/[0.06] text-[#F5F5F7]/85 text-[11px]">
                          {(res.confidence_score * 100).toFixed(0)}% match
                        </span>
                      )}
                      <span
                        className={`px-2.5 py-0.5 rounded-full font-medium text-[11px] capitalize ${
                          res.status === "injected"
                            ? "bg-[#34C759]/20 text-[#34C759]"
                            : "bg-white/[0.08] text-[#F5F5F7]/80"
                        }`}
                      >
                        {res.status.replace("_", " ")}
                      </span>
                      {meta && (
                        <button
                          onClick={() =>
                            setExpandedRow(isExpanded ? null : i)
                          }
                          className="p-1 rounded-md hover:bg-white/[0.08] text-[#86868B] hover:text-[#F5F5F7]"
                          title="Inspect resolved tags"
                        >
                          {isExpanded ? (
                            <ChevronUp className="w-3.5 h-3.5" />
                          ) : (
                            <ChevronDown className="w-3.5 h-3.5" />
                          )}
                        </button>
                      )}
                    </div>
                  </div>

                  {isExpanded && meta && (
                    <div className="pt-2 border-t border-white/[0.07] grid grid-cols-2 sm:grid-cols-3 gap-2 text-[11px] tabular-nums">
                      <div className="text-[#86868B]">
                        Year:{" "}
                        <span className="text-[#F5F5F7]">
                          {meta.year || meta.date || "—"}
                        </span>
                      </div>
                      <div className="text-[#86868B]">
                        Label:{" "}
                        <span className="text-[#F5F5F7]">
                          {meta.label || "—"}
                        </span>
                      </div>
                      <div className="text-[#86868B]">
                        Barcode:{" "}
                        <span className="text-[#F5F5F7] font-mono">
                          {meta.barcode || "—"}
                        </span>
                      </div>
                      <div className="col-span-full text-[#86868B]">
                        Genres:{" "}
                        <span className="text-[#F5F5F7]">
                          {meta.genre?.length ? meta.genre.join(", ") : "—"}
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};