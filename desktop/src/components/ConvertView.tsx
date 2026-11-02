import React, { useState } from "react";
import { Disc, FolderOpen, CheckCircle2, AlertCircle } from "lucide-react";
import { ConvertItemResult, ProgressEvent, ScanItem } from "../types/injector";
import { pickLibraryFolder } from "../lib/tauriClient";

interface ConvertViewProps {
  items: ScanItem[];
  isConverting: boolean;
  currentProgress: ProgressEvent | null;
  lastResults: ConvertItemResult[];
  onStartConvert: (params: {
    paths: string[];
    outputDir?: string | null;
    inject: boolean;
    deleteOriginal: boolean;
    compressionLevel: number;
    threshold: number;
    dryRun: boolean;
  }) => void;
}

export const ConvertView: React.FC<ConvertViewProps> = ({
  items,
  isConverting,
  currentProgress,
  lastResults,
  onStartConvert,
}) => {
  const [compressionLevel, setCompressionLevel] = useState<number>(8);
  const [outputDir, setOutputDir] = useState<string>("");
  const [injectAfter, setInjectAfter] = useState<boolean>(true);
  const [deleteOriginal, setDeleteOriginal] = useState<boolean>(false);
  const [dryRun, setDryRun] = useState<boolean>(false);

  const wavFiles = items.filter((i) =>
    ["wav", "wave", "aiff", "aif"].includes(i.audio_format.toLowerCase())
  );

  const handleSelectOutputFolder = async () => {
    try {
      const folder = await pickLibraryFolder();
      if (folder) setOutputDir(folder);
    } catch (e) {
      console.error("Select output folder error:", e);
    }
  };

  const handleConvert = () => {
    onStartConvert({
      paths: wavFiles.map((w) => w.path),
      outputDir: outputDir ? outputDir : null,
      inject: injectAfter,
      deleteOriginal,
      compressionLevel,
      threshold: 0.7,
      dryRun,
    });
  };

  return (
    <div className="flex flex-col h-full space-y-4 overflow-y-auto pr-1">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Compression Level Card */}
        <div className="p-4 rounded-2xl glass-panel flex flex-col justify-between space-y-4">
          <div className="flex justify-between items-center">
            <div>
              <div className="text-xs font-semibold text-[#F5F5F7]">
                FLAC lossless compression
              </div>
              <div className="text-xs text-[#A1A1A6] mt-0.5">
                All levels preserve 100% bit-identical PCM audio
              </div>
            </div>
            <span className="text-xs font-semibold tabular-nums text-[#0A84FF] bg-[#0A84FF]/15 px-2.5 py-1 rounded-lg border border-[#0A84FF]/30">
              Level {compressionLevel}
            </span>
          </div>

          <div className="space-y-2">
            <input
              type="range"
              min="0"
              max="12"
              step="1"
              value={compressionLevel}
              onChange={(e) => setCompressionLevel(parseInt(e.target.value, 10))}
              className="w-full apple-slider"
            />
            <div className="flex justify-between text-xs text-[#A1A1A6] tabular-nums">
              <span>0 (Fastest)</span>
              <span className="text-[#F5F5F7] font-medium">8 (Standard)</span>
              <span>12 (Maximum)</span>
            </div>
          </div>
        </div>

        {/* Output Destination Card */}
        <div className="p-4 rounded-2xl glass-panel flex flex-col justify-between space-y-3">
          <div>
            <div className="text-xs font-semibold text-[#F5F5F7]">
              Destination folder
            </div>
            <div className="text-xs text-[#A1A1A6] mt-0.5">
              Choose where encoded masters are written
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <input
              type="text"
              readOnly
              value={outputDir || "Same folder as source WAV"}
              className="flex-1 px-3 py-1.5 rounded-lg bg-black/40 border border-white/[0.08] text-xs text-[#F5F5F7] focus:outline-none"
            />
            <button
              type="button"
              onClick={handleSelectOutputFolder}
              className="apple-btn-secondary px-3 py-1.5 rounded-lg text-xs font-medium flex items-center space-x-1.5"
            >
              <FolderOpen className="w-3.5 h-3.5 text-[#0A84FF]" />
              <span>Choose…</span>
            </button>
          </div>
        </div>
      </div>

      {/* Switch Rows */}
      <div className="p-4 rounded-2xl glass-panel divide-y divide-white/[0.06]">
        {[
          {
            label: "Auto-inject metadata and artwork",
            desc: "Immediately run the provider waterfall on newly encoded FLAC files",
            checked: injectAfter,
            setChecked: setInjectAfter,
          },
          {
            label: "Remove source WAV after verification",
            desc: "Delete original uncompressed WAV only after FLAC integrity check",
            checked: deleteOriginal,
            setChecked: setDeleteOriginal,
          },
          {
            label: "Dry-run simulation",
            desc: "Preview target FLAC paths without encoding audio",
            checked: dryRun,
            setChecked: setDryRun,
          },
        ].map((row) => (
          <div
            key={row.label}
            onClick={() => row.setChecked(!row.checked)}
            className="flex items-center justify-between py-2.5 cursor-pointer group"
          >
            <div>
              <div className="text-xs font-medium text-[#F5F5F7] group-hover:text-white">
                {row.label}
              </div>
              <div className="text-xs text-[#A1A1A6] mt-0.5">{row.desc}</div>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={row.checked}
              className={`w-9 h-5 rounded-full p-0.5 transition-colors duration-150 shrink-0 ${
                row.checked ? "bg-[#34C759]" : "bg-white/[0.14]"
              }`}
            >
              <div
                className={`w-4 h-4 rounded-full bg-white shadow-sm transform transition-transform duration-150 ${
                  row.checked ? "translate-x-4" : "translate-x-0"
                }`}
              />
            </button>
          </div>
        ))}
      </div>

      {/* Live Progress Bar */}
      {isConverting && (
        <div className="p-4 rounded-2xl glass-panel space-y-2 border border-[#0A84FF]/40">
          <div className="flex justify-between text-xs tabular-nums">
            <span className="text-[#F5F5F7] font-medium truncate max-w-lg">
              {currentProgress?.message || "Encoding audio files to lossless FLAC…"}
            </span>
            <span className="text-[#0A84FF] font-semibold">
              {currentProgress?.percent?.toFixed(0) || 0}%
            </span>
          </div>
          <div className="w-full h-1.5 rounded-full bg-white/[0.08] overflow-hidden">
            <div
              className="h-full bg-[#0A84FF] transition-all duration-150 rounded-full"
              style={{ width: `${currentProgress?.percent || 0}%` }}
            />
          </div>
        </div>
      )}

      {/* Action Bar */}
      <div className="flex items-center justify-between p-4 rounded-2xl glass-panel">
        <span className="text-xs text-[#A1A1A6] tabular-nums">
          <span className="text-[#F5F5F7] font-semibold">{wavFiles.length}</span>{" "}
          uncompressed WAV file(s) queued
        </span>

        <button
          type="button"
          onClick={handleConvert}
          disabled={isConverting || wavFiles.length === 0}
          className="apple-btn-primary flex items-center space-x-2 px-5 py-2 rounded-lg text-xs font-semibold disabled:opacity-40"
        >
          <Disc className="w-4 h-4" />
          <span>
            {isConverting
              ? "Encoding…"
              : `Encode to lossless FLAC (${wavFiles.length})`}
          </span>
        </button>
      </div>

      {/* Output Log */}
      {lastResults.length > 0 && (
        <div className="space-y-2">
          {lastResults.map((res, i) => (
            <div
              key={i}
              className="p-3.5 rounded-xl surface-elevated flex items-center justify-between text-xs"
            >
              <div className="flex items-center space-x-2.5 truncate max-w-md">
                {res.status === "converted" ? (
                  <CheckCircle2 className="w-4 h-4 text-[#34C759] shrink-0" />
                ) : (
                  <AlertCircle className="w-4 h-4 text-[#FF453A] shrink-0" />
                )}
                <span className="truncate text-[#F5F5F7] font-mono text-xs">
                  {res.destination || res.source}
                </span>
              </div>
              <span className="text-[#34C759] capitalize font-medium text-xs">
                {res.status}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
