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
          transition={{ duration: 0.18 }}
          onClick={onClose}
          className="fixed inset-0 z-50 flex items-center justify-end p-4 bg-black/55 backdrop-blur-sm"
        >
          <motion.div
            key="inspect-sheet"
            initial={{ x: 48, opacity: 0, scale: 0.97 }}
            animate={{ x: 0, opacity: 1, scale: 1 }}
            exit={{ x: 40, opacity: 0, scale: 0.97 }}
            transition={{ type: "spring", duration: 0.35, bounce: 0 }}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-xl h-full rounded-[24px] glass-panel shadow-2xl flex flex-col p-6 space-y-5 overflow-hidden"
          >
            {/* Sheet Header */}
            <div className="flex items-center justify-between border-b border-white/[0.08] pb-4">
              <div className="min-w-0 pr-4">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-[#0A84FF]">
                  Track Inspector
                </span>
                <h2 className="text-base display-heading text-[#F5F5F7] truncate mt-0.5">
                  {item.existing_tags.TITLE?.[0] || item.filename}
                </h2>
                <p className="text-xs text-[#86868B] truncate">
                  {item.existing_tags.ARTIST?.[0] || "Unknown Artist"}
                </p>
              </div>
              <div className="flex items-center space-x-1.5 shrink-0">
                {totalCount > 1 && (
                  <div className="flex items-center space-x-1 mr-2 text-[11px] text-[#86868B]">
                    <span className="tabular-nums font-medium mr-1 text-[#F5F5F7]">
                      {currentIndex + 1} of {totalCount}
                    </span>
                    <button
                      onClick={() => onNavigate?.("prev")}
                      title="Previous Track (←)"
                      className="w-7 h-7 rounded-full bg-white/[0.08] hover:bg-white/[0.15] active:scale-[0.95] flex items-center justify-center text-[#86868B] hover:text-[#F5F5F7] transition-all"
                    >
                      <ChevronLeft className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => onNavigate?.("next")}
                      title="Next Track (→)"
                      className="w-7 h-7 rounded-full bg-white/[0.08] hover:bg-white/[0.15] active:scale-[0.95] flex items-center justify-center text-[#86868B] hover:text-[#F5F5F7] transition-all"
                    >
                      <ChevronRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}
                <button
                  onClick={onClose}
                  className="w-8 h-8 rounded-full bg-white/[0.08] hover:bg-white/[0.15] active:scale-[0.95] flex items-center justify-center text-[#86868B] hover:text-[#F5F5F7] transition-all shrink-0"
                  title="Close Inspector (Esc)"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Scrollable Inspector Body */}
            <div className="flex-1 overflow-y-auto space-y-5 pr-1">
              {/* Hero Artwork + Apple Music Lossless Spec Card (Concentric: 16px inside 24px) */}
              <div className="flex items-center space-x-5 p-4 rounded-[16px] surface-elevated">
                <div
                  onClick={() => item.cover_art_data_url && setZoomArt(true)}
                  className="relative group w-28 h-28 rounded-[12px] overflow-hidden bg-black/40 border border-white/[0.12] shrink-0 flex items-center justify-center shadow-lg cursor-pointer"
                >
                  {item.cover_art_data_url ? (
                    <>
                      <img
                        src={item.cover_art_data_url}
                        alt="Album Cover"
                        className="w-full h-full object-cover transition-transform duration-200 group-hover:scale-105"
                      />
                      <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                        <Maximize2 className="w-5 h-5 text-white" />
                      </div>
                    </>
                  ) : (
                    <span className="text-[11px] text-[#86868B]">No Artwork</span>
                  )}
                </div>

                <div className="flex-1 min-w-0 space-y-2">
                  <div className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-[8px] bg-white/[0.08] border border-white/[0.12] text-[11px] font-medium text-[#F5F5F7]">
                    <AudioWaveform className="w-3.5 h-3.5 text-[#0A84FF]" />
                    <span>
                      {item.audio_format === "mp3"
                        ? "MPEG Audio"
                        : item.bits_per_sample > 16 || item.sample_rate > 48000
                          ? "Hi-Res Lossless"
                          : "Lossless"}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs tabular-nums">
                    <div className="text-[#86868B]">
                      Resolution:{" "}
                      <span className="text-[#F5F5F7] font-medium">
                        {item.bits_per_sample}-bit /{" "}
                        {(item.sample_rate / 1000).toFixed(1)} kHz
                      </span>
                    </div>
                    <div className="text-[#86868B]">
                      Duration:{" "}
                      <span className="text-[#F5F5F7] font-medium">
                        {Math.floor(item.duration_seconds / 60)}:
                        {Math.floor(item.duration_seconds % 60)
                          .toString()
                          .padStart(2, "0")}
                      </span>
                    </div>
                    <div className="text-[#86868B]">
                      Channels:{" "}
                      <span className="text-[#F5F5F7] font-medium">
                        {item.channels === 2 ? "Stereo" : `${item.channels} Ch`}
                      </span>
                    </div>
                    <div className="text-[#86868B]">
                      Cover Art:{" "}
                      <span className="text-[#F5F5F7] font-medium">
                        {item.cover_art_info
                          ? `${item.cover_art_info.width}×${item.cover_art_info.height}`
                          : "Missing"}
                      </span>
                    </div>
                  </div>

                  <div className="text-[11px] font-mono text-[#86868B]/70 truncate pt-1">
                    {item.path}
                  </div>
                </div>
              </div>

              {/* Chromaprint Acoustic Fingerprint Card */}
              <div className="p-4 rounded-[16px] surface-elevated space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Fingerprint className="w-4 h-4 text-[#0A84FF]" />
                    <span className="text-xs font-semibold text-[#F5F5F7]">
                      Chromaprint Acoustic Fingerprint
                    </span>
                  </div>
                  <button
                    onClick={handleComputeFingerprint}
                    disabled={fpLoading}
                    className="apple-btn-secondary px-3 py-1 rounded-[8px] text-[11px] font-medium text-[#F5F5F7] disabled:opacity-50"
                  >
                    {fpLoading
                      ? "Computing via fpcalc…"
                      : fpData
                        ? "Recompute"
                        : "Generate Fingerprint"}
                  </button>
                </div>

                {fpError && (
                  <div className="text-[11px] text-[#FF453A] bg-[#FF453A]/10 border border-[#FF453A]/30 rounded-[10px] px-3 py-2">
                    {fpError}
                  </div>
                )}

                {fpData && (
                  <div className="space-y-2 text-xs">
                    <div className="flex items-center justify-between bg-black/35 border border-white/[0.08] rounded-[10px] px-3 py-2">
                      <span className="font-mono text-[11px] text-[#F5F5F7]/85 truncate mr-3">
                        {fpData.fingerprint}
                      </span>
                      <button
                        onClick={handleCopyFingerprint}
                        className="text-[#86868B] hover:text-[#F5F5F7] shrink-0 flex items-center space-x-1 text-[11px]"
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
                              className="px-2 py-0.5 rounded-[6px] bg-white/[0.06] text-[10px] text-[#86868B]"
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
                  <span className="text-xs font-semibold text-[#F5F5F7]/90">
                    {item.audio_format === "flac"
                      ? "Vorbis Comment Header"
                      : "ID3v2.4 Frame Header"}
                  </span>
                  <span className="text-[11px] text-[#86868B] tabular-nums">
                    {Object.keys(item.existing_tags).length} fields
                  </span>
                </div>

                <div className="rounded-[16px] surface-elevated overflow-hidden divide-y divide-white/[0.05]">
                  {Object.entries(item.existing_tags).length === 0 ? (
                    <div className="py-8 text-center text-xs text-[#86868B]">
                      No metadata tags embedded in this file.
                    </div>
                  ) : (
                    Object.entries(item.existing_tags).map(([key, vals]) => (
                      <div
                        key={key}
                        className="flex items-baseline justify-between px-4 py-2 text-xs hover:bg-white/[0.03]"
                      >
                        <span className="font-mono text-[11px] text-[#86868B] w-44 shrink-0">
                          {key}
                        </span>
                        <span className="text-[#F5F5F7] font-medium text-right break-all">
                          {vals.join(", ")}
                        </span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>

            {/* Sheet Footer */}
            <div className="border-t border-white/[0.08] pt-4 flex items-center justify-between">
              <span className="text-xs text-[#86868B] tabular-nums">
                {item.is_incomplete
                  ? `${item.missing_fields.length} core field(s) missing`
                  : "All canonical fields verified"}
              </span>
              <button
                onClick={() => onInject(item)}
                className="apple-btn-primary flex items-center space-x-2 px-5 py-2 rounded-[12px] text-white text-xs font-semibold"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Resolve & Inject Track</span>
              </button>
            </div>
          </motion.div>

          {/* 3000px Master Artwork Lightbox */}
          <AnimatePresence>
            {zoomArt && item.cover_art_data_url && (
              <motion.div
                key="art-lightbox"
                initial={{ opacity: 0, scale: 0.96 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.96 }}
                transition={{ type: "spring", duration: 0.3, bounce: 0 }}
                onClick={() => setZoomArt(false)}
                className="fixed inset-0 z-[60] flex items-center justify-center bg-black/85 backdrop-blur-xl p-8"
              >
                <div
                  onClick={(e) => e.stopPropagation()}
                  className="relative max-w-2xl max-h-[88vh] rounded-[24px] overflow-hidden glass-panel p-3 shadow-2xl"
                >
                  <button
                    onClick={() => setZoomArt(false)}
                    className="absolute top-5 right-5 z-10 w-8 h-8 rounded-full bg-black/60 text-white flex items-center justify-center hover:bg-black active:scale-[0.95]"
                  >
                    <X className="w-4 h-4" />
                  </button>
                  <img
                    src={item.cover_art_data_url}
                    alt="3000px Master Artwork"
                    className="w-full h-full object-contain rounded-[16px] max-h-[82vh]"
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