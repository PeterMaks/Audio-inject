import React, { useState } from "react";
import { X, Sparkles, Maximize2, AudioWaveform } from "lucide-react";
import { ScanItem } from "../types/injector";

interface InspectDrawerProps {
  item: ScanItem | null;
  onClose: () => void;
  onInject: (item: ScanItem) => void;
}

export const InspectDrawer: React.FC<InspectDrawerProps> = ({
  item,
  onClose,
  onInject,
}) => {
  const [zoomArt, setZoomArt] = useState(false);

  if (!item) return null;

  const minutes = Math.floor(item.duration_seconds / 60);
  const seconds = Math.floor(item.duration_seconds % 60);
  const sampleRateKhz = (item.sample_rate / 1000).toFixed(1);
  const isHiRes = item.bits_per_sample > 16 || item.sample_rate > 48000;

  return (
    <div
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-center justify-end p-4 bg-black/50 backdrop-blur-sm transition-opacity"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-xl h-full rounded-3xl glass-panel border border-white/[0.16] shadow-2xl flex flex-col p-6 space-y-5 overflow-hidden"
      >
        {/* Sheet Header */}
        <div className="flex items-center justify-between border-b border-white/[0.08] pb-4">
          <div className="min-w-0 pr-4">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-[#0A84FF]">
              Track Inspector
            </span>
            <h2 className="text-base font-semibold text-white truncate mt-0.5">
              {item.existing_tags.TITLE?.[0] || item.filename}
            </h2>
            <p className="text-xs text-white/50 truncate">
              {item.existing_tags.ARTIST?.[0] || "Unknown Artist"}
            </p>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-full bg-white/[0.08] hover:bg-white/[0.15] flex items-center justify-center text-white/70 hover:text-white transition-colors shrink-0"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Scrollable Inspector Body */}
        <div className="flex-1 overflow-y-auto space-y-5 pr-1">
          {/* Hero Artwork + Apple Music Lossless Spec Card */}
          <div className="flex items-center space-x-5 p-4 rounded-2xl bg-white/[0.03] border border-white/[0.08]">
            <div
              onClick={() => item.cover_art_data_url && setZoomArt(true)}
              className="relative group w-28 h-28 rounded-2xl overflow-hidden bg-black/40 border border-white/[0.12] shrink-0 flex items-center justify-center shadow-xl cursor-pointer"
            >
              {item.cover_art_data_url ? (
                <>
                  <img
                    src={item.cover_art_data_url}
                    alt="Album Cover"
                    className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
                  />
                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                    <Maximize2 className="w-5 h-5 text-white" />
                  </div>
                </>
              ) : (
                <span className="text-[11px] text-white/40">No Artwork</span>
              )}
            </div>

            <div className="flex-1 min-w-0 space-y-2">
              {/* Official Apple Music Style Lossless Badge */}
              <div className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-md bg-white/[0.08] border border-white/[0.12] text-[11px] font-medium text-white/90">
                <AudioWaveform className="w-3.5 h-3.5 text-[#0A84FF]" />
                <span>
                  {item.audio_format === "mp3"
                    ? "MPEG Audio"
                    : isHiRes
                      ? "Hi-Res Lossless"
                      : "Lossless"}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs tabular-nums">
                <div className="text-white/45">
                  Resolution:{" "}
                  <span className="text-white/90 font-medium">
                    {item.bits_per_sample}-bit / {sampleRateKhz} kHz
                  </span>
                </div>
                <div className="text-white/45">
                  Duration:{" "}
                  <span className="text-white/90 font-medium">
                    {minutes}:{seconds.toString().padStart(2, "0")}
                  </span>
                </div>
                <div className="text-white/45">
                  Channels:{" "}
                  <span className="text-white/90 font-medium">
                    {item.channels === 2 ? "Stereo" : `${item.channels} Ch`}
                  </span>
                </div>
                <div className="text-white/45">
                  Cover Art:{" "}
                  <span className="text-white/90 font-medium">
                    {item.cover_art_info
                      ? `${item.cover_art_info.width}×${item.cover_art_info.height}`
                      : "Missing"}
                  </span>
                </div>
              </div>

              <div className="text-[11px] font-mono text-white/35 truncate pt-1">
                {item.path}
              </div>
            </div>
          </div>

          {/* Embedded Frame / Vorbis Table */}
          <div className="space-y-2">
            <div className="flex items-center justify-between px-1">
              <span className="text-xs font-semibold text-white/80">
                {item.audio_format === "flac"
                  ? "Vorbis Comment Header"
                  : "ID3v2.4 Frame Header"}
              </span>
              <span className="text-[11px] text-white/40 tabular-nums">
                {Object.keys(item.existing_tags).length} fields
              </span>
            </div>

            <div className="rounded-2xl border border-white/[0.08] bg-black/25 overflow-hidden divide-y divide-white/[0.05]">
              {Object.entries(item.existing_tags).length === 0 ? (
                <div className="py-8 text-center text-xs text-white/40">
                  No metadata tags embedded in this file.
                </div>
              ) : (
                Object.entries(item.existing_tags).map(([key, vals]) => (
                  <div
                    key={key}
                    className="flex items-baseline justify-between px-4 py-2 text-xs hover:bg-white/[0.02]"
                  >
                    <span className="font-mono text-[11px] text-white/45 w-44 shrink-0">
                      {key}
                    </span>
                    <span className="text-white/90 font-medium text-right break-all">
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
          <span className="text-xs text-white/45">
            {item.is_incomplete
              ? `${item.missing_fields.length} core field(s) missing`
              : "All canonical fields verified"}
          </span>
          <button
            onClick={() => onInject(item)}
            className="apple-btn-primary flex items-center space-x-2 px-5 py-2 rounded-xl text-white text-xs font-semibold"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Resolve & Inject Track</span>
          </button>
        </div>
      </div>

      {/* 3000px Master Artwork Lightbox */}
      {zoomArt && item.cover_art_data_url && (
        <div
          onClick={() => setZoomArt(false)}
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/85 backdrop-blur-xl p-8"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="relative max-w-2xl max-h-[88vh] rounded-3xl overflow-hidden glass-panel p-3 shadow-2xl"
          >
            <button
              onClick={() => setZoomArt(false)}
              className="absolute top-5 right-5 z-10 w-8 h-8 rounded-full bg-black/60 text-white flex items-center justify-center hover:bg-black"
            >
              <X className="w-4 h-4" />
            </button>
            <img
              src={item.cover_art_data_url}
              alt="3000px Master Artwork"
              className="w-full h-full object-contain rounded-2xl max-h-[82vh]"
            />
          </div>
        </div>
      )}
    </div>
  );
};  