import React, { useState, useMemo, useDeferredValue, useCallback } from "react";
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

interface TrackRowProps {
  item: ScanItem;
  isSelected: boolean;
  onToggleSelect: (path: string) => void;
  onInspect: (item: ScanItem) => void;
  onInjectSingle: (item: ScanItem) => void;
  onConvertSingle: (item: ScanItem) => void;
}

const TrackRow = React.memo(function TrackRow({
  item,
  isSelected,
  onToggleSelect,
  onInspect,
  onInjectSingle,
  onConvertSingle,
}: TrackRowProps) {
  const title = item.existing_tags.TITLE?.[0] || item.filename;
  const artist = item.existing_tags.ARTIST?.join(", ") || "Unknown Artist";
  const album = item.existing_tags.ALBUM?.[0] || "—";
  const mins = Math.floor(item.duration_seconds / 60);
  const secs = Math.floor(item.duration_seconds % 60);
  const isWav = ["wav", "wave", "aiff", "aif"].includes(item.audio_format.toLowerCase());

  return (
    <tr
      onDoubleClick={() => onInspect(item)}
      className={`transition-colors cursor-default ${
        isSelected
          ? "bg-[#0A84FF]/15 hover:bg-[#0A84FF]/20"
          : "hover:bg-[#1F1F1F]"
      }`}
    >
      <td className="py-2.5 pl-4 pr-2">
        <button
          type="button"
          onClick={() => onToggleSelect(item.path)}
          className="text-[#A1A1A6] hover:text-[#F5F5F7] flex items-center p-0.5 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0A84FF]"
          title="Select track"
        >
          {isSelected ? (
            <CheckSquare className="w-4 h-4 text-[#0A84FF]" />
          ) : (
            <Square className="w-4 h-4" />
          )}
        </button>
      </td>

      {/* Title, Artist & Specs */}
      <td className="py-2.5 px-3 max-w-xs">
        <div className="font-medium text-[#F5F5F7] truncate text-xs">{title}</div>
        <div className="text-xs text-[#A1A1A6] truncate tabular-nums">
          {artist} • {mins}:{secs.toString().padStart(2, "0")} •{" "}
          <span className="font-mono text-xs text-[#6E6E73]">
            {item.filename}
          </span>
        </div>
      </td>

      {/* Album */}
      <td className="py-2.5 px-3 text-[#A1A1A6] truncate max-w-[180px] text-xs">
        {album}
      </td>

      {/* Format Badge */}
      <td className="py-2.5 px-3 text-center tabular-nums">
        <span className="inline-block px-2 py-0.5 rounded-md text-xs font-semibold uppercase tracking-wide bg-white/[0.08] text-[#F5F5F7] border border-white/[0.08]">
          {item.audio_format}
        </span>
      </td>

      {/* Artwork Resolution */}
      <td className="py-2.5 px-3 text-center tabular-nums">
        {item.has_cover_art && item.cover_art_info ? (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-md bg-[#34C759]/15 text-[#34C759] text-xs font-medium">
            <ImageIcon className="w-3.5 h-3.5" />
            <span>
              {item.cover_art_info.width}×{item.cover_art_info.height}
            </span>
          </span>
        ) : (
          <span className="inline-block px-2 py-0.5 rounded-md bg-white/[0.06] text-[#A1A1A6] text-xs">
            None
          </span>
        )}
      </td>

      {/* Status */}
      <td className="py-2.5 px-3 text-center">
        {item.is_incomplete ? (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full bg-[#FF9F0A]/15 text-[#FF9F0A] font-medium text-xs">
            <AlertCircle className="w-3.5 h-3.5" />
            <span>Incomplete</span>
          </span>
        ) : (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full bg-[#34C759]/15 text-[#34C759] font-medium text-xs">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Complete</span>
          </span>
        )}
      </td>

      {/* Missing Fields */}
      <td className="py-2.5 px-3">
        {item.missing_fields.length > 0 ? (
          <div className="flex flex-wrap gap-1 max-w-xs">
            {item.missing_fields.slice(0, 3).map((f) => (
              <span
                key={f}
                className="px-1.5 py-0.5 rounded-md bg-white/[0.06] text-[#A1A1A6] text-xs font-medium"
              >
                {f}
              </span>
            ))}
            {item.missing_fields.length > 3 && (
              <span className="px-1.5 py-0.5 rounded-md bg-white/[0.04] text-[#6E6E73] text-xs tabular-nums">
                +{item.missing_fields.length - 3}
              </span>
            )}
          </div>
        ) : (
          <span className="text-[#6E6E73] text-xs">—</span>
        )}
      </td>

      {/* Row Actions */}
      <td className="py-2.5 px-4 text-right">
        <div className="flex items-center justify-end space-x-1.5">
          <button
            type="button"
            onClick={() => onInspect(item)}
            title="Inspect track"
            className="apple-btn-secondary p-1.5 rounded-lg text-[#A1A1A6] hover:text-[#F5F5F7]"
          >
            <Eye className="w-3.5 h-3.5" />
          </button>
          {isWav ? (
            <button
              type="button"
              onClick={() => onConvertSingle(item)}
              title="Encode WAV to FLAC"
              className="apple-btn-secondary p-1.5 rounded-lg text-[#FF9F0A]"
            >
              <Disc className="w-3.5 h-3.5" />
            </button>
          ) : (
            <button
              type="button"
              onClick={() => onInjectSingle(item)}
              title="Inject metadata"
              className="apple-btn-primary p-1.5 rounded-lg text-white"
            >
              <Sparkles className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </td>
    </tr>
  );
});

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

  // React 19 deferred value: search input stays 0ms responsive under heavy library loads
  const deferredQuery = useDeferredValue(searchQuery);

  const handleSort = useCallback(
    (key: SortKey) => {
      if (sortKey === key) {
        setSortAsc(!sortAsc);
      } else {
        setSortKey(key);
        setSortAsc(true);
      }
      setCurrentPage(1);
    },
    [sortKey, sortAsc]
  );

  const filteredItems = useMemo(() => {
    const query = deferredQuery.trim().toLowerCase();
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
        const artist = item.existing_tags.ARTIST?.join(" ")?.toLowerCase() || "";
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

    if (base.length <= 1) return base;

    const dir = sortAsc ? 1 : -1;
    return [...base].sort((a, b) => {
      if (sortKey === "title") {
        const tA = a.existing_tags.TITLE?.[0] || a.filename;
        const tB = b.existing_tags.TITLE?.[0] || b.filename;
        return tA.localeCompare(tB, undefined, { sensitivity: "base" }) * dir;
      }
      if (sortKey === "album") {
        const alA = a.existing_tags.ALBUM?.[0] || "";
        const alB = b.existing_tags.ALBUM?.[0] || "";
        return alA.localeCompare(alB, undefined, { sensitivity: "base" }) * dir;
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
  }, [items, filterFormat, onlyIncomplete, deferredQuery, sortKey, sortAsc]);

  const totalPages = Math.max(1, Math.ceil(filteredItems.length / PAGE_SIZE));
  const safePage = Math.min(currentPage, totalPages);

  const paginatedItems = useMemo(() => {
    const start = (safePage - 1) * PAGE_SIZE;
    return filteredItems.slice(start, start + PAGE_SIZE);
  }, [filteredItems, safePage]);

  // Single-pass computation for batch actions
  const { selectedItems, selectedWavItems, incompleteCount } = useMemo(() => {
    const sel: ScanItem[] = [];
    const wav: ScanItem[] = [];
    let inc = 0;

    for (const item of items) {
      if (item.is_incomplete) inc++;
      if (selectedPaths.has(item.path)) {
        sel.push(item);
        const fmt = item.audio_format.toLowerCase();
        if (fmt === "wav" || fmt === "wave" || fmt === "aiff" || fmt === "aif") {
          wav.push(item);
        }
      }
    }
    return {
      selectedItems: sel,
      selectedWavItems: wav,
      incompleteCount: inc,
    };
  }, [items, selectedPaths]);

  const allFilteredSelected =
    filteredItems.length > 0 &&
    filteredItems.every((i) => selectedPaths.has(i.path));

  const toggleSelectAllFiltered = useCallback(() => {
    if (allFilteredSelected) {
      onClearSelection();
    } else {
      onSelectMany(filteredItems.map((i) => i.path));
    }
  }, [allFilteredSelected, filteredItems, onClearSelection, onSelectMany]);

  return (
    <div className="flex flex-col h-full space-y-3">
      {/* Concentric Filter Bar: Outer rounded-2xl (16px), Inner rounded-lg (8px) */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-2xl glass-panel">
        <div className="flex flex-wrap items-center gap-2.5">
          {/* Search Field */}
          <div className="relative w-64">
            <Search className="w-3.5 h-3.5 text-[#A1A1A6] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              placeholder="Search title, artist, album"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setCurrentPage(1);
              }}
              className="w-full pl-8 pr-7 py-1.5 rounded-lg bg-black/40 border border-white/[0.08] text-xs text-[#F5F5F7] placeholder-[#6E6E73] focus:outline-none focus:border-[#0A84FF] focus:ring-1 focus:ring-[#0A84FF] transition-colors"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => {
                  setSearchQuery("");
                  setCurrentPage(1);
                }}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#A1A1A6] hover:text-[#F5F5F7] p-0.5 rounded"
                title="Clear search"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>

          {/* Segmented Control */}
          <div className="flex items-center apple-segmented">
            {["all", "flac", "mp3", "wav"].map((fmt) => {
              const active = filterFormat === fmt;
              return (
                <button
                  key={fmt}
                  type="button"
                  onClick={() => {
                    setFilterFormat(fmt);
                    setCurrentPage(1);
                  }}
                  className={`relative px-3 py-1 text-xs font-medium uppercase transition-colors rounded-md ${
                    active
                      ? "text-[#F5F5F7]"
                      : "text-[#A1A1A6] hover:text-[#F5F5F7]"
                  }`}
                >
                  {active && (
                    <motion.div
                      layoutId="scan-format-segmented"
                      transition={{ type: "spring", duration: 0.24, bounce: 0 }}
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
            type="button"
            onClick={() => {
              setOnlyIncomplete(!onlyIncomplete);
              setCurrentPage(1);
            }}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all tabular-nums ${
              onlyIncomplete
                ? "bg-[#FF9F0A]/20 text-[#FF9F0A] border-[#FF9F0A]/40"
                : "bg-white/[0.04] text-[#A1A1A6] border-white/[0.08] hover:text-[#F5F5F7]"
            }`}
          >
            Incomplete ({incompleteCount})
          </button>
        </div>

        {/* Batch Actions */}
        <div className="flex items-center space-x-2">
          {selectedItems.length > 0 ? (
            <>
              <span className="text-xs text-[#A1A1A6] tabular-nums px-1">
                {selectedItems.length} selected
              </span>
              {selectedWavItems.length > 0 && (
                <button
                  type="button"
                  onClick={() => onConvertBatch(selectedWavItems)}
                  className="apple-btn-secondary flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-[#FF9F0A] text-xs font-medium tabular-nums"
                >
                  <Disc className="w-3.5 h-3.5" />
                  <span>Encode WAVs ({selectedWavItems.length})</span>
                </button>
              )}
              <button
                type="button"
                onClick={() => onInjectBatch(selectedItems)}
                className="apple-btn-primary flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg text-white text-xs font-semibold tabular-nums"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Inject selected ({selectedItems.length})</span>
              </button>
            </>
          ) : (
            incompleteCount > 0 && (
              <button
                type="button"
                onClick={() => onInjectBatch(items.filter((i) => i.is_incomplete))}
                className="apple-btn-primary flex items-center space-x-1.5 px-4 py-1.5 rounded-lg text-white text-xs font-semibold tabular-nums"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Auto-tag incomplete ({incompleteCount})</span>
              </button>
            )
          )}
        </div>
      </div>

      {/* Tracklist Table */}
      <div className="flex-1 overflow-auto rounded-2xl glass-panel">
        <table className="w-full text-left border-collapse">
          <thead className="sticky top-0 bg-[#181818] border-b border-white/[0.08] z-10 text-xs text-[#A1A1A6] font-medium select-none">
            <tr>
              <th className="py-2.5 pl-4 pr-2 w-8">
                <button
                  type="button"
                  onClick={toggleSelectAllFiltered}
                  className="text-[#A1A1A6] hover:text-[#F5F5F7] flex items-center p-0.5 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0A84FF]"
                  title="Select all visible tracks"
                >
                  {allFilteredSelected ? (
                    <CheckSquare className="w-4 h-4 text-[#0A84FF]" />
                  ) : (
                    <Square className="w-4 h-4" />
                  )}
                </button>
              </th>
              <th
                onClick={() => handleSort("title")}
                className="py-2.5 px-3 cursor-pointer hover:text-[#F5F5F7] transition-colors"
              >
                <div className="flex items-center space-x-1">
                  <span>Track</span>
                  <ArrowUpDown className="w-3 h-3 opacity-60" />
                </div>
              </th>
              <th
                onClick={() => handleSort("album")}
                className="py-2.5 px-3 cursor-pointer hover:text-[#F5F5F7] transition-colors"
              >
                <div className="flex items-center space-x-1">
                  <span>Album</span>
                  <ArrowUpDown className="w-3 h-3 opacity-60" />
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
              <th className="py-2.5 px-3">Missing tags</th>
              <th className="py-2.5 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.05] text-xs">
            {filteredItems.length === 0 ? (
              <tr>
                <td colSpan={8} className="py-16 text-center text-[#A1A1A6] text-xs">
                  No tracks match your current filter.
                </td>
              </tr>
            ) : (
              paginatedItems.map((item) => (
                <TrackRow
                  key={item.path}
                  item={item}
                  isSelected={selectedPaths.has(item.path)}
                  onToggleSelect={onToggleSelect}
                  onInspect={onInspect}
                  onInjectSingle={onInjectSingle}
                  onConvertSingle={onConvertSingle}
                />
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-3.5 py-2 rounded-xl glass-panel text-xs text-[#A1A1A6] shrink-0">
          <span>
            Showing{" "}
            <span className="text-[#F5F5F7] font-medium">
              {(safePage - 1) * PAGE_SIZE + 1}–
              {Math.min(safePage * PAGE_SIZE, filteredItems.length)}
            </span>{" "}
            of{" "}
            <span className="text-[#F5F5F7] font-medium">
              {filteredItems.length}
            </span>{" "}
            tracks
          </span>
          <div className="flex items-center space-x-2">
            <button
              type="button"
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={safePage <= 1}
              className="apple-btn-secondary flex items-center space-x-1 px-2.5 py-1 rounded-lg disabled:opacity-30 disabled:pointer-events-none"
              title="Previous page"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
              <span>Prev</span>
            </button>
            <span className="tabular-nums px-1 text-[#F5F5F7] font-medium">
              Page {safePage} of {totalPages}
            </span>
            <button
              type="button"
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={safePage >= totalPages}
              className="apple-btn-secondary flex items-center space-x-1 px-2.5 py-1 rounded-lg disabled:opacity-30 disabled:pointer-events-none"
              title="Next page"
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
