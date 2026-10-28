import React, { useState, useMemo } from "react";
import { motion } from "framer-motion";
import {
  CheckCircle2,
  AlertCircle,
  Image as ImageIcon,
  Sparkles,
  Eye,
  Disc,
  Search,
  X,
  ArrowUpDown,
  CheckSquare,
  Square,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { ScanItem } from "../types/injector";

interface ScanViewProps {
  items: ScanItem[];
  selectedPaths: Set<string>;
  onToggleSelect: (path: string) => void;
  onSelectMany: (paths: string[]) => void;
  onClearSelection: () => void;
  onInspect: (item: ScanItem) => void;
  onInjectSingle: (item: ScanItem) => void;
  onInjectBatch: (items: ScanItem[]) => void;
  onConvertSingle: (item: ScanItem) => void;
  onConvertBatch: (items: ScanItem[]) => void;
}

type SortKey = "title" | "album" | "format" | "artwork" | "status";

export const ScanView: React.FC<ScanViewProps> = ({
  items,
  selectedPaths,
  onToggleSelect,
  onSelectMany,
  onClearSelection,
  onInspect,
  onInjectSingle,
  onInjectBatch,
  onConvertSingle,
  onConvertBatch,
}) => {
  const [filterFormat, setFilterFormat] = useState<string>("all");
  const [onlyIncomplete, setOnlyIncomplete] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [sortKey, setSortKey] = useState<SortKey>("title");
  const [sortAsc, setSortAsc] = useState<boolean>(true);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const PAGE_SIZE = 100;

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(true);
    }
    setCurrentPage(1);
  };

  const filteredItems = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    const base = items.filter((item) => {
      if (
        filterFormat !== "all" &&
        item.audio_format.toLowerCase() !== filterFormat
      ) {
        return false;
      }
      if (onlyIncomplete && !item.is_incomplete) {
        return false;
      }
      if (query) {
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

    return [...base].sort((a, b) => {
      const dir = sortAsc ? 1 : -1;
      if (sortKey === "title") {
        const tA = (a.existing_tags.TITLE?.[0] || a.filename).toLowerCase();
        const tB = (b.existing_tags.TITLE?.[0] || b.filename).toLowerCase();
        return tA.localeCompare(tB) * dir;
      }
      if (sortKey === "album") {
        const alA = (a.existing_tags.ALBUM?.[0] || "").toLowerCase();
        const alB = (b.existing_tags.ALBUM?.[0] || "").toLowerCase();
        return alA.localeCompare(alB) * dir;
      }
      if (sortKey === "format") {
        return a.audio_format.localeCompare(b.audio_format) * dir;
      }
      if (sortKey === "artwork") {
        const resA = a.cover_art_info?.width || 0;
        const resB = b.cover_art_info?.width || 0;
        return (resA - resB) * dir;
      }
      if (sortKey === "status") {
        return (Number(a.is_incomplete) - Number(b.is_incomplete)) * dir;
      }
      return 0;
    });
  }, [items, filterFormat, onlyIncomplete, searchQuery, sortKey, sortAsc]);

  const totalPages = Math.max(1, Math.ceil(filteredItems.length / PAGE_SIZE));
  const safePage = Math.min(currentPage, totalPages);

  const paginatedItems = useMemo(() => {
    const start = (safePage - 1) * PAGE_SIZE;
    return filteredItems.slice(start, start + PAGE_SIZE);
  }, [filteredItems, safePage]);

  const incompleteItems = useMemo(
    () => items.filter((item) => item.is_incomplete),
    [items]
  );

  const selectedItems = useMemo(
    () => items.filter((item) => selectedPaths.has(item.path)),
    [items, selectedPaths]
  );

  const selectedWavItems = useMemo(
    () =>
      selectedItems.filter((i) =>
        ["wav", "wave", "aiff", "aif"].includes(i.audio_format.toLowerCase())
      ),
    [selectedItems]
  );

  const allFilteredSelected =
    filteredItems.length > 0 &&
    filteredItems.every((i) => selectedPaths.has(i.path));

  const toggleSelectAllFiltered = () => {
    if (allFilteredSelected) {
      onClearSelection();
    } else {
      onSelectMany(filteredItems.map((i) => i.path));
    }
  };

  return (
    <div className="flex flex-col h-full space-y-3.5">
      {/* Concentric Filter Bar: Outer rounded-[20px] p-2 -> Inner controls rounded-[12px] */}
      <div className="flex flex-wrap items-center justify-between gap-2.5 p-2.5 rounded-[20px] glass-panel">
        <div className="flex flex-wrap items-center gap-2.5">
          {/* Spotlight Search Field */}
          <div className="relative w-60">
            <Search className="w-3.5 h-3.5 text-[#86868B] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              placeholder="Search title, artist, album…"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setCurrentPage(1);
              }}
              className="w-full pl-8 pr-7 py-1.5 rounded-[12px] bg-black/35 border border-white/[0.08] text-xs text-[#F5F5F7] placeholder-[#86868B] focus:outline-none focus:border-[#0A84FF] transition-colors"
            />
            {searchQuery && (
              <button
                onClick={() => {
                  setSearchQuery("");
                  setCurrentPage(1);
                }}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#86868B] hover:text-[#F5F5F7]"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>

          {/* Animated Apple Segmented Control */}
          <div className="flex items-center apple-segmented">
            {["all", "flac", "mp3", "wav"].map((fmt) => {
              const active = filterFormat === fmt;
              return (
                <button
                  key={fmt}
                  onClick={() => {
                    setFilterFormat(fmt);
                    setCurrentPage(1);
                  }}
                  className={`relative px-3 py-1 text-xs font-medium uppercase transition-colors ${
                    active
                      ? "text-[#F5F5F7]"
                      : "text-[#86868B] hover:text-[#F5F5F7]/80"
                  }`}
                >
                  {active && (
                    <motion.div
                      layoutId="scan-format-segmented"
                      transition={{ type: "spring", duration: 0.28, bounce: 0 }}
                      className="absolute inset-0 apple-segmented-pill"
                    />
                  )}
                  <span className="relative z-10">{fmt}</span>
                </button>
              );
            })}
          </div>

          {/* Incomplete Filter Pill */}
          <button
            onClick={() => {
              setOnlyIncomplete(!onlyIncomplete);
              setCurrentPage(1);
            }}
            className={`px-3 py-1.5 rounded-[12px] text-xs font-medium border transition-all tabular-nums active:scale-[0.97] ${
              onlyIncomplete
                ? "bg-[#FF9F0A]/20 text-[#FF9F0A] border-[#FF9F0A]/40"
                : "bg-white/[0.04] text-[#86868B] border-white/[0.08] hover:text-[#F5F5F7]"
            }`}
          >
            Incomplete ({incompleteItems.length})
          </button>
        </div>

        {/* Contextual Batch Actions */}
        <div className="flex items-center space-x-2">
          {selectedItems.length > 0 ? (
            <>
              <span className="text-[11px] text-[#86868B] tabular-nums px-1">
                {selectedItems.length} selected
              </span>
              {selectedWavItems.length > 0 && (
                <button
                  onClick={() => onConvertBatch(selectedWavItems)}
                  className="apple-btn-secondary flex items-center space-x-1.5 px-3 py-1.5 rounded-[12px] text-[#FF9F0A] text-xs font-medium tabular-nums"
                >
                  <Disc className="w-3.5 h-3.5" />
                  <span>Encode WAVs ({selectedWavItems.length})</span>
                </button>
              )}
              <button
                onClick={() => onInjectBatch(selectedItems)}
                className="apple-btn-primary flex items-center space-x-1.5 px-3.5 py-1.5 rounded-[12px] text-white text-xs font-semibold tabular-nums"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Inject Selected ({selectedItems.length})</span>
              </button>
            </>
          ) : (
            incompleteItems.length > 0 && (
              <button
                onClick={() => onInjectBatch(incompleteItems)}
                className="apple-btn-primary flex items-center space-x-1.5 px-4 py-1.5 rounded-[12px] text-white text-xs font-semibold tabular-nums"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Auto-Tag Incomplete ({incompleteItems.length})</span>
              </button>
            )
          )}
        </div>
      </div>

      {/* Apple Music Style Tracklist Table */}
      <div className="flex-1 overflow-auto rounded-[20px] glass-panel">
        <table className="w-full text-left border-collapse">
          <thead className="sticky top-0 bg-[#1C1C1E]/95 backdrop-blur-xl border-b border-white/[0.08] z-10 text-[11px] text-[#86868B] font-medium select-none">
            <tr>
              <th className="py-2.5 pl-4 pr-2 w-8">
                <button
                  onClick={toggleSelectAllFiltered}
                  className="text-[#86868B] hover:text-[#F5F5F7] flex items-center"
                  title="Select all visible tracks"
                >
                  {allFilteredSelected ? (
                    <CheckSquare className="w-3.5 h-3.5 text-[#0A84FF]" />
                  ) : (
                    <Square className="w-3.5 h-3.5" />
                  )}
                </button>
              </th>
              <th
                onClick={() => handleSort("title")}
                className="py-2.5 px-3 cursor-pointer hover:text-[#F5F5F7] transition-colors"
              >
                <div className="flex items-center space-x-1">
                  <span>Track</span>
                  <ArrowUpDown className="w-3 h-3 opacity-50" />
                </div>
              </th>
              <th
                onClick={() => handleSort("album")}
                className="py-2.5 px-3 cursor-pointer hover:text-[#F5F5F7] transition-colors"
              >
                <div className="flex items-center space-x-1">
                  <span>Album</span>
                  <ArrowUpDown className="w-3 h-3 opacity-50" />
                </div>
              </th>
              <th
                onClick={() => handleSort("format")}
                className="py-2.5 px-3 text-center cursor-pointer hover:text-[#F5F5F7] transition-colors"
              >
                Format
              </th>
              <th
                onClick={() => handleSort("artwork")}
                className="py-2.5 px-3 text-center cursor-pointer hover:text-[#F5F5F7] transition-colors"
              >
                Artwork
              </th>
              <th
                onClick={() => handleSort("status")}
                className="py-2.5 px-3 text-center cursor-pointer hover:text-[#F5F5F7] transition-colors"
              >
                Status
              </th>
              <th className="py-2.5 px-3">Missing Tags</th>
              <th className="py-2.5 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.05] text-xs">
            {filteredItems.length === 0 ? (
              <tr>
                <td colSpan={8} className="py-16 text-center text-[#86868B]">
                  No tracks match your current filter.
                </td>
              </tr>
            ) : (
              paginatedItems.map((item) => {
                const title = item.existing_tags.TITLE?.[0] || item.filename;
                const artist =
                  item.existing_tags.ARTIST?.[0] || "Unknown Artist";
                const album = item.existing_tags.ALBUM?.[0] || "—";
                const isSelected = selectedPaths.has(item.path);
                const mins = Math.floor(item.duration_seconds / 60);
                const secs = Math.floor(item.duration_seconds % 60);

                return (
                  <tr
                    key={item.path}
                    onDoubleClick={() => onInspect(item)}
                    className={`transition-colors group cursor-default ${
                      isSelected
                        ? "bg-[#0A84FF]/10 hover:bg-[#0A84FF]/15"
                        : "hover:bg-white/[0.04]"
                    }`}
                  >
                    <td className="py-2.5 pl-4 pr-2">
                      <button
                        onClick={() => onToggleSelect(item.path)}
                        className="text-[#86868B] hover:text-[#F5F5F7] flex items-center"
                      >
                        {isSelected ? (
                          <CheckSquare className="w-3.5 h-3.5 text-[#0A84FF]" />
                        ) : (
                          <Square className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </td>

                    {/* Title, Artist & Specs */}
                    <td className="py-2.5 px-3 max-w-xs">
                      <div className="font-medium text-[#F5F5F7] truncate">
                        {title}
                      </div>
                      <div className="text-[11px] text-[#86868B] truncate tabular-nums">
                        {artist} • {mins}:{secs.toString().padStart(2, "0")} •{" "}
                        <span className="font-mono text-[10px] text-[#86868B]/70">
                          {item.filename}
                        </span>
                      </div>
                    </td>

                    {/* Album */}
                    <td className="py-2.5 px-3 text-[#F5F5F7]/75 truncate max-w-[180px]">
                      {album}
                    </td>

                    {/* Format Badge */}
                    <td className="py-2.5 px-3 text-center tabular-nums">
                      <span className="inline-block px-2 py-0.5 rounded-[6px] text-[10px] font-semibold uppercase tracking-wide bg-white/[0.07] text-[#F5F5F7]/90 border border-white/[0.08]">
                        {item.audio_format}
                      </span>
                    </td>

                    {/* Artwork Resolution */}
                    <td className="py-2.5 px-3 text-center tabular-nums">
                      {item.has_cover_art && item.cover_art_info ? (
                        <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-[6px] bg-[#34C759]/15 text-[#34C759] text-[11px] font-medium">
                          <ImageIcon className="w-3 h-3" />
                          <span>
                            {item.cover_art_info.width}×
                            {item.cover_art_info.height}
                          </span>
                        </span>
                      ) : (
                        <span className="inline-block px-2 py-0.5 rounded-[6px] bg-white/[0.05] text-[#86868B] text-[11px]">
                          None
                        </span>
                      )}
                    </td>

                    {/* Status */}
                    <td className="py-2.5 px-3 text-center">
                      {item.is_incomplete ? (
                        <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full bg-[#FF9F0A]/15 text-[#FF9F0A] font-medium text-[11px]">
                          <AlertCircle className="w-3 h-3" />
                          <span>Incomplete</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full bg-[#34C759]/15 text-[#34C759] font-medium text-[11px]">
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
                              className="px-1.5 py-0.5 rounded-[5px] bg-white/[0.06] text-[#F5F5F7]/70 text-[10px] font-medium"
                            >
                              {f}
                            </span>
                          ))}
                          {item.missing_fields.length > 4 && (
                            <span className="px-1.5 py-0.5 rounded-[5px] bg-white/[0.04] text-[#86868B] text-[10px] tabular-nums">
                              +{item.missing_fields.length - 4}
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className="text-[#86868B]/50">—</span>
                      )}
                    </td>

                    {/* Row Actions */}
                    <td className="py-2.5 px-4 text-right">
                      <div className="flex items-center justify-end space-x-1.5">
                        <button
                          onClick={() => onInspect(item)}
                          title="Inspect Track & Acoustic Fingerprint"
                          className="apple-btn-secondary p-1.5 rounded-[8px] text-[#86868B] hover:text-[#F5F5F7]"
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </button>
                        {item.audio_format.toLowerCase() === "wav" ? (
                          <button
                            onClick={() => onConvertSingle(item)}
                            title="Encode WAV to FLAC"
                            className="apple-btn-secondary p-1.5 rounded-[8px] text-[#FF9F0A]"
                          >
                            <Disc className="w-3.5 h-3.5" />
                          </button>
                        ) : (
                          <button
                            onClick={() => onInjectSingle(item)}
                            title="Inject Metadata"
                            className="apple-btn-primary p-1.5 rounded-[8px] text-white"
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

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-3 py-2 rounded-[14px] glass-panel text-xs text-[#86868B] shrink-0">
          <span>
            Showing <span className="text-[#F5F5F7] font-medium">{(safePage - 1) * PAGE_SIZE + 1}–{Math.min(safePage * PAGE_SIZE, filteredItems.length)}</span> of{" "}
            <span className="text-[#F5F5F7] font-medium">{filteredItems.length}</span> tracks
          </span>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={safePage <= 1}
              className="apple-btn-secondary flex items-center space-x-1 px-2.5 py-1 rounded-[8px] disabled:opacity-30 disabled:pointer-events-none"
              title="Previous Page"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
              <span>Prev</span>
            </button>
            <span className="tabular-nums px-1 text-[#F5F5F7] font-medium">
              Page {safePage} of {totalPages}
            </span>
            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={safePage >= totalPages}
              className="apple-btn-secondary flex items-center space-x-1 px-2.5 py-1 rounded-[8px] disabled:opacity-30 disabled:pointer-events-none"
              title="Next Page"
            >
              <span>Next</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};