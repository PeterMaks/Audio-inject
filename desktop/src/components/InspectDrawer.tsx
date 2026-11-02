import React, { useState, useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  X,
  Sparkles,
  Maximize2,
  AudioWaveform,
  Fingerprint,
  Copy,
  Check,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { FingerprintResponse, ScanItem } from "../types/injector";
import { runFingerprint } from "../lib/tauriClient";

interface InspectDrawerProps {
  item: ScanItem | null;
  currentIndex?: number;
  totalCount?: number;
  onClose: () => void;
  onInject: (item: ScanItem) => void;
  onNavigate?: (direction: "prev" | "next") => void;
}

export const InspectDrawer: React.FC<InspectDrawerProps> = ({
  item,
  currentIndex = 0,
  totalCount = 0,
  onClose,
  onInject,
  onNavigate,
}) => {
  const [zoomArt, setZoomArt] = useState(false);
  const [fpData, setFpData] = useState<FingerprintResponse | null>(null);
  const [fpLoading, setFpLoading] = useState(false);
  const [fpError, setFpError] = useState<string | null>(null);
  const [copiedFp, setCopiedFp] = useState(false);

  useEffect(() => {
    if (!item) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      } else if (e.key === "ArrowLeft") {
        onNavigate?.("prev");
      } else if (e.key === "ArrowRight") {
        onNavigate?.("next");
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [item, onClose, onNavigate]);

  useEffect(() => {
    setFpData(null);
    setFpError(null);
    setCopiedFp(false);
  }, [item?.path]);

  const handleComputeFingerprint = async () => {
    if (!item) return;
    setFpLoading(true);
    setFpError(null);
    try {
      const res = await runFingerprint(item.path);
      setFpData(res);
    } catch (err) {
      setFpError(String(err));
    } finally {
      setFpLoading(false);
    }
  };

  const handleCopyFingerprint = () => {
    if (!fpData?.fingerprint) return;
    navigator.clipboard.writeText(fpData.fingerprint);
    setCopiedFp(true);
    setTimeout(() => setCopiedFp(false), 2000);
  };

  return (
    <AnimatePresence>
      {item && (
        <motion.div
          key="inspect-backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.16 }}
          onClick={onClose}
          className="fixed inset-0 z-50 flex items-center justify-end p-4 bg-black/60"
        >
          <motion.div
            key="inspect-sheet"
            initial={{ x: 40, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 32, opacity: 0 }}
            transition={{ type: "spring", duration: 0.3, bounce: 0 }}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-xl h-full rounded-2xl glass-panel shadow-2xl flex flex-col p-5 space-y-4 overflow-hidden border border-white/10"
          >
            {/* Sheet Header */}
            <div className="flex items-center justify-between border-b border-white/[0.08] pb-3.5">
              <div className="min-w-0 pr-3">
                <span className="text-xs font-semibold uppercase tracking-wider text-[#0A84FF]">
                  Track inspector
                </span>
                <h2 className="text-base display-heading text-[#F5F5F7] truncate mt-0.5">
                  {item.existing_tags.TITLE?.[0] || item.filename}
                </h2>
                <p className="text-xs text-[#A1A1A6] truncate">
                  {item.existing_tags.ARTIST?.join(", ") || "Unknown Artist"}
                </p>
              </div>
              <div className="flex items-center space-x-1.5 shrink-0">
                {totalCount > 1 && (
                  <div className="flex items-center space-x-1 mr-2 text-xs text-[#A1A1A6]">
                    <span className="tabular-nums font-medium mr-1 text-[#F5F5F7]">
                      {currentIndex + 1} of {totalCount}
                    </span>
                    <button
                      type="button"
                      onClick={() => onNavigate?.("prev")}
                      title="Previous track (Left Arrow)"
                      className="w-7 h-7 rounded-lg bg-white/[0.08] hover:bg-white/[0.14] active:scale-[0.98] flex items-center justify-center text-[#A1A1A6] hover:text-[#F5F5F7] transition-all"
                    >
                      <ChevronLeft className="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => onNavigate?.("next")}
                      title="Next track (Right Arrow)"
                      className="w-7 h-7 rounded-lg bg-white/[0.08] hover:bg-white/[0.14] active:scale-[0.98] flex items-center justify-center text-[#A1A1A6] hover:text-[#F5F5F7] transition-all"
                    >
                      <ChevronRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}
                <button
                  type="button"
                  onClick={onClose}
                  className="w-7 h-7 rounded-lg bg-white/[0.08] hover:bg-white/[0.14] active:scale-[0.98] flex items-center justify-center text-[#A1A1A6] hover:text-[#F5F5F7] transition-all shrink-0"
                  title="Close (Esc)"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {/* Scrollable Body */}
            <div className="flex-1 overflow-y-auto space-y-4 pr-1">
              {/* Specs Hero Card */}
              <div className="flex items-center space-x-4 p-4 rounded-xl surface-elevated">
                <div
                  onClick={() => item.cover_art_data_url && setZoomArt(true)}
                  className="relative group w-24 h-24 rounded-lg overflow-hidden bg-black/40 border border-white/[0.12] shrink-0 flex items-center justify-center shadow-md cursor-pointer"
                >
                  {item.cover_art_data_url ? (
                    <>
                      <img
                        src={item.cover_art_data_url}
                        alt="Album cover"
                        className="w-full h-full object-cover transition-transform duration-150 group-hover:scale-105"
                      />
                      <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                        <Maximize2 className="w-4 h-4 text-white" />
                      </div>
                    </>
                  ) : (
                    <span className="text-xs text-[#A1A1A6]">No artwork</span>
                  )}
                </div>

                <div className="flex-1 min-w-0 space-y-2">
                  <div className="inline-flex items-center space-x-1.5 px-2 py-0.5 rounded-md bg-white/[0.08] border border-white/[0.12] text-xs font-medium text-[#F5F5F7]">
                    <AudioWaveform className="w-3 h-3 text-[#0A84FF]" />
                    <span>
                      {item.audio_format === "mp3"
                        ? "MPEG Audio"
                        : item.bits_per_sample > 16 || item.sample_rate > 48000
                          ? "Hi-Res Lossless"
                          : "Lossless PCM"}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs tabular-nums">
                    <div className="text-[#A1A1A6]">
                      Resolution:{" "}
                      <span className="text-[#F5F5F7] font-medium">
                        {item.bits_per_sample}-bit /{" "}
                        {(item.sample_rate / 1000).toFixed(1)} kHz
                      </span>
                    </div>
                    <div className="text-[#A1A1A6]">
                      Duration:{" "}
                      <span className="text-[#F5F5F7] font-medium">
                        {Math.floor(item.duration_seconds / 60)}:
                        {Math.floor(item.duration_seconds % 60)
                          .toString()
                          .padStart(2, "0")}
                      </span>
                    </div>
                    <div className="text-[#A1A1A6]">
                      Channels:{" "}
                      <span className="text-[#F5F5F7] font-medium">
                        {item.channels === 2 ? "Stereo" : `${item.channels} Ch`}
                      </span>
                    </div>
                    <div className="text-[#A1A1A6]">
                      Artwork:{" "}
                      <span className="text-[#F5F5F7] font-medium">
                        {item.cover_art_info
                          ? `${item.cover_art_info.width}×${item.cover_art_info.height}`
                          : "Missing"}
                      </span>
                    </div>
                  </div>

                  <div className="text-xs font-mono text-[#6E6E73] truncate pt-0.5">
                    {item.path}
                  </div>
                </div>
              </div>

              {/* Chromaprint Fingerprint Card */}
              <div className="p-4 rounded-xl surface-elevated space-y-2.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Fingerprint className="w-4 h-4 text-[#0A84FF]" />
                    <span className="text-xs font-semibold text-[#F5F5F7]">
                      Chromaprint acoustic fingerprint
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={handleComputeFingerprint}
                    disabled={fpLoading}
                    className="apple-btn-secondary px-3 py-1 rounded-lg text-xs font-medium text-[#F5F5F7] disabled:opacity-50"
                  >
                    {fpLoading
                      ? "Computing via fpcalc…"
                      : fpData
                        ? "Recompute"
                        : "Generate fingerprint"}
                  </button>
                </div>

                {fpError && (
                  <div className="text-xs text-[#FF453A] bg-[#FF453A]/10 border border-[#FF453A]/30 rounded-lg px-3 py-2">
                    {fpError}
                  </div>
                )}

                {fpData && (
                  <div className="space-y-2 text-xs">
                    <div className="flex items-center justify-between bg-black/40 border border-white/[0.08] rounded-lg px-3 py-1.5">
                      <span className="font-mono text-xs text-[#F5F5F7] truncate mr-3">
                        {fpData.fingerprint}
                      </span>
                      <button
                        type="button"
                        onClick={handleCopyFingerprint}
                        className="text-[#A1A1A6] hover:text-[#F5F5F7] shrink-0 flex items-center space-x-1 text-xs"
                        title="Copy fingerprint"
                      >
                        {copiedFp ? (
                          <Check className="w-3.5 h-3.5 text-[#34C759]" />
                        ) : (
                          <Copy className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </div>
                    {fpData.hints && Object.keys(fpData.hints).length > 0 && (
                      <div className="flex flex-wrap gap-1.5 pt-0.5">
                        {Object.entries(fpData.hints).map(([k, v]) =>
                          v ? (
                            <span
                              key={k}
                              className="px-2 py-0.5 rounded-md bg-white/[0.06] text-xs text-[#A1A1A6]"
                            >
                              {k}: <strong className="text-[#F5F5F7]">{String(v)}</strong>
                            </span>
                          ) : null
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Embedded Frame / Vorbis Table */}
              <div className="space-y-2">
                <div className="flex items-center justify-between px-1">
                  <span className="text-xs font-semibold text-[#F5F5F7]">
                    {item.audio_format === "flac"
                      ? "Vorbis comment header"
                      : "ID3v2.4 frame header"}
                  </span>
                  <span className="text-xs text-[#A1A1A6] tabular-nums">
                    {Object.keys(item.existing_tags).length} fields
                  </span>
                </div>

                <div className="rounded-xl surface-elevated overflow-hidden divide-y divide-white/[0.05]">
                  {Object.entries(item.existing_tags).length === 0 ? (
                    <div className="py-6 text-center text-xs text-[#A1A1A6]">
                      No metadata tags embedded in this file.
                    </div>
                  ) : (
                    Object.entries(item.existing_tags).map(([key, vals]) => (
                      <div
                        key={key}
                        className="flex items-baseline justify-between px-3.5 py-1.5 text-xs hover:bg-white/[0.03]"
                      >
                        <span className="font-mono text-xs text-[#A1A1A6] w-40 shrink-0">
                          {key}
                        </span>
                        <span className="text-[#F5F5F7] font-medium text-right break-all text-xs">
                          {vals.join(", ")}
                        </span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>

            {/* Sheet Footer */}
            <div className="border-t border-white/[0.08] pt-3.5 flex items-center justify-between">
              <span className="text-xs text-[#A1A1A6] tabular-nums">
                {item.is_incomplete
                  ? `${item.missing_fields.length} core field(s) missing`
                  : "All canonical fields verified"}
              </span>
              <button
                type="button"
                onClick={() => onInject(item)}
                className="apple-btn-primary flex items-center space-x-2 px-4 py-2 rounded-lg text-white text-xs font-semibold"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Resolve and inject track</span>
              </button>
            </div>
          </motion.div>

          {/* Master Artwork Lightbox */}
          <AnimatePresence>
            {zoomArt && item.cover_art_data_url && (
              <motion.div
                key="art-lightbox"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.98 }}
                transition={{ type: "spring", duration: 0.25, bounce: 0 }}
                onClick={() => setZoomArt(false)}
                className="fixed inset-0 z-[60] flex items-center justify-center bg-black/85 p-6"
              >
                <div
                  onClick={(e) => e.stopPropagation()}
                  className="relative max-w-2xl max-h-[85vh] rounded-2xl overflow-hidden glass-panel p-2 shadow-2xl"
                >
                  <button
                    type="button"
                    onClick={() => setZoomArt(false)}
                    className="absolute top-4 right-4 z-10 w-7 h-7 rounded-lg bg-black/70 text-white flex items-center justify-center hover:bg-black"
                    title="Close preview"
                  >
                    <X className="w-4 h-4" />
                  </button>
                  <img
                    src={item.cover_art_data_url}
                    alt="Master artwork"
                    className="w-full h-full object-contain rounded-xl max-h-[80vh]"
                  />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      )}
    </AnimatePresence>
  );
};
