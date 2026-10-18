import React, { useState, useMemo } from "react";
import {
  CheckCircle2,
  AlertCircle,
  Image as ImageIcon,
  Sparkles,
  Eye,
  Disc,
  Search,
  X,
} from "lucide-react";
import { ScanItem } from "../types/injector";

interface ScanViewProps {
  items: ScanItem[];
  onInspect: (item: ScanItem) => void;
  onInjectSingle: (item: ScanItem) => void;
  onInjectBatch: (items: ScanItem[]) => void;
  onConvertSingle: (item: ScanItem) => void;
}

export const ScanView: React.FC<ScanViewProps> = ({
  items,
  onInspect,
  onInjectSingle,
  onInjectBatch,
  onConvertSingle,
}) => {
  const [filterFormat, setFilterFormat] = useState<string>("all");
  const [onlyIncomplete, setOnlyIncomplete] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>("");

  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      if (
        filterFormat !== "all" &&
        item.audio_format.toLowerCase() !== filterFormat
      ) {
        return false;
      }
      if (onlyIncomplete && !item.is_incomplete) {
        return false;
      }
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        const title = item.existing_tags.TITLE?.[0]?.toLowerCase() || "";
        const artist = item.existing_tags.ARTIST?.[0]?.toLowerCase() || "";
        const album = item.existing_tags.ALBUM?.[0]?.toLowerCase() || "";
        const filename = item.filename.toLowerCase();
        if (
          !title.includes(query) &&
          !artist.includes(query) &&
          !album.includes(query) &&
          !filename.includes(query)
        ) {
          return false;
        }
      }
      return true;
    });
  }, [items, filterFormat, onlyIncomplete, searchQuery]);

  const incompleteItems = useMemo(
    () => items.filter((item) => item.is_incomplete),
    [items]
  );

  return (
    <div className="flex flex-col h-full space-y-4">
      {/* Apple HIG Filter Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-2xl glass-panel">
        <div className="flex items-center space-x-3">
          {/* Spotlight-style Search Field */}
          <div className="relative w-64">
            <Search className="w-3.5 h-3.5 text-white/40 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              placeholder="Search title, artist, album…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-7 py-1.5 rounded-lg bg-black/30 border border-white/[0.08] text-xs text-white placeholder-white/35 focus:outline-none focus:border-[#0A84FF]"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-white/40 hover:text-white"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>

          {/* Apple Segmented Control */}
          <div className="flex items-center p-0.5 rounded-lg apple-segmented">
            {["all", "flac", "mp3", "wav"].map((fmt) => (
              <button
                key={fmt}
                onClick={() => setFilterFormat(fmt)}
                className={`px-3 py-1 rounded-md text-xs font-medium uppercase transition-all ${filterFormat === fmt
                    ? "apple-segmented-item-active text-white"
                    : "text-white/55 hover:text-white/85"
                  }`}
              >
                {fmt}
              </button>
            ))}
          </div>

          {/* Incomplete Filter Pill */}
          <button
            onClick={() => setOnlyIncomplete(!onlyIncomplete)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all tabular-nums ${onlyIncomplete
                ? "bg-[#FF453A]/20 text-[#FF6961] border-[#FF453A]/40"
                : "bg-white/[0.04] text-white/65 border-white/[0.08] hover:text-white"
              }`}
          >
            Incomplete Only ({incompleteItems.length})
          </button>
        </div>

        {/* Primary Batch Action */}
        {incompleteItems.length > 0 && (
          <button
            onClick={() => onInjectBatch(incompleteItems)}
            className="apple-btn-primary flex items-center space-x-1.5 px-4 py-1.5 rounded-lg text-white text-xs font-semibold tabular-nums"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Auto-Tag Incomplete ({incompleteItems.length})</span>
          </button>
        )}
      </div>

      {/* Apple Music Style Tracklist Table */}
      <div className="flex-1 overflow-auto rounded-2xl glass-panel">
        <table className="w-full text-left border-collapse">
          <thead className="sticky top-0 bg-[#18181f]/90 backdrop-blur-xl border-b border-white/[0.07] z-10 text-[11px] text-white/45 font-medium">
            <tr>
              <th className="py-2.5 px-4">Track</th>
              <th className="py-2.5 px-3">Album</th>
              <th className="py-2.5 px-3 text-center">Format</th>
              <th className="py-2.5 px-3 text-center">Artwork</th>
              <th className="py-2.5 px-3 text-center">Status</th>
              <th className="py-2.5 px-3">Missing Tags</th>
              <th className="py-2.5 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.04] text-xs">
            {filteredItems.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-14 text-center text-white/40">
                  No tracks match your current filter.
                </td>
              </tr>
            ) : (
              filteredItems.map((item) => {
                const title = item.existing_tags.TITLE?.[0] || item.filename;
                const artist = item.existing_tags.ARTIST?.[0] || "Unknown Artist";
                const album = item.existing_tags.ALBUM?.[0] || "—";

                return (
                  <tr
                    key={item.path}
                    onDoubleClick={() => onInspect(item)}
                    className="hover:bg-white/[0.04] transition-colors group cursor-default"
                  >
                    {/* Title, Artist & Filename */}
                    <td className="py-2.5 px-4 max-w-xs">
                      <div className="font-medium text-white truncate">
                        {title}
                      </div>
                      <div className="text-[11px] text-white/50 truncate">
                        {artist} •{" "}
                        <span className="font-mono text-[10px] text-white/35">
                          {item.filename}
                        </span>
                      </div>
                    </td>

                    {/* Album */}
                    <td className="py-2.5 px-3 text-white/70 truncate max-w-[180px]">
                      {album}
                    </td>

                    {/* Format Badge */}
                    <td className="py-2.5 px-3 text-center">
                      <span className="inline-block px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wide bg-white/[0.07] text-white/85 border border-white/[0.08]">
                        {item.audio_format}
                      </span>
                    </td>

                    {/* Artwork Resolution */}
                    <td className="py-2.5 px-3 text-center tabular-nums">
                      {item.has_cover_art && item.cover_art_info ? (
                        <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-md bg-[#30D158]/15 text-[#30D158] text-[11px] font-medium">
                          <ImageIcon className="w-3 h-3" />
                          <span>
                            {item.cover_art_info.width}×{item.cover_art_info.height}
                          </span>
                        </span>
                      ) : (
                        <span className="inline-block px-2 py-0.5 rounded-md bg-white/[0.05] text-white/40 text-[11px]">
                          None
                        </span>
                      )}
                    </td>

                    {/* Status */}
                    <td className="py-2.5 px-3 text-center">
                      {item.is_incomplete ? (
                        <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full bg-[#FF9F0A]/15 text-[#FF9F0A] font-medium text-[11px]">
                          <AlertCircle className="w-3 h-3" />
                          <span>Incomplete</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full bg-[#30D158]/15 text-[#30D158] font-medium text-[11px]">
                          <CheckCircle2 className="w-3 h-3" />
                          <span>Complete</span>
                        </span>
                      )}
                    </td>

                    {/* Missing Fields */}
                    <td className="py-2.5 px-3">
                      {item.missing_fields.length > 0 ? (
                        <div className="flex flex-wrap gap-1 max-w-xs">
                          {item.missing_fields.slice(0, 4).map((f) => (
                            <span
                              key={f}
                              className="px-1.5 py-0.5 rounded bg-white/[0.06] text-white/65 text-[10px] font-medium"
                            >
                              {f}
                            </span>
                          ))}
                          {item.missing_fields.length > 4 && (
                            <span className="px-1.5 py-0.5 rounded bg-white/[0.04] text-white/45 text-[10px]">
                              +{item.missing_fields.length - 4}
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className="text-white/30">—</span>
                      )}
                    </td>

                    {/* Row Actions */}
                    <td className="py-2.5 px-4 text-right">
                      <div className="flex items-center justify-end space-x-1.5">
                        <button
                          onClick={() => onInspect(item)}
                          title="Inspect Track"
                          className="apple-btn-secondary p-1.5 rounded-lg text-white/70 hover:text-white"
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </button>
                        {item.audio_format === "wav" ? (
                          <button
                            onClick={() => onConvertSingle(item)}
                            title="Encode WAV to FLAC"
                            className="apple-btn-secondary p-1.5 rounded-lg text-[#FF9F0A]"
                          >
                            <Disc className="w-3.5 h-3.5" />
                          </button>
                        ) : (
                          <button
                            onClick={() => onInjectSingle(item)}
                            title="Inject Metadata"
                            className="apple-btn-primary p-1.5 rounded-lg text-white"
                          >
                            <Sparkles className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};