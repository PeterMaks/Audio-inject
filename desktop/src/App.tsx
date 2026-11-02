import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Plus,
  FolderPlus,
  CheckCircle2,
  AlertCircle,
  X,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { Titlebar } from "./components/Titlebar";
import { Sidebar, ActiveTab } from "./components/Sidebar";
import { DropZone } from "./components/DropZone";
import { ScanView } from "./components/ScanView";
import { InspectDrawer } from "./components/InspectDrawer";
import { InjectView } from "./components/InjectView";
import { ConvertView } from "./components/ConvertView";
import { SettingsModal } from "./components/SettingsModal";
import {
  ConvertItemResult,
  InjectItemResult,
  ProgressEvent,
  ScanItem,
} from "./types/injector";
import {
  onInjectorProgress,
  pickAudioFiles,
  pickLibraryFolder,
  runConvert,
  runInject,
  runInspect,
  runScan,
} from "./lib/tauriClient";

interface AppleToast {
  id: number;
  type: "success" | "error" | "info";
  title: string;
  message: string;
}

const MAX_INSPECT_CACHE = 50;

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<ActiveTab>("scan");
  const [scannedItems, setScannedItems] = useState<ScanItem[]>([]);
  const [selectedPaths, setSelectedPaths] = useState<Set<string>>(new Set());
  const [inspectedItem, setInspectedItem] = useState<ScanItem | null>(null);
  const [ambientArtUrl, setAmbientArtUrl] = useState<string | null>(null);
  const [recursiveScan, setRecursiveScan] = useState<boolean>(true);

  const [isScanning, setIsScanning] = useState<boolean>(false);
  const [isInjecting, setIsInjecting] = useState<boolean>(false);
  const [isConverting, setIsConverting] = useState<boolean>(false);

  const [currentProgress, setCurrentProgress] = useState<ProgressEvent | null>(null);
  const [injectResults, setInjectResults] = useState<InjectItemResult[]>([]);
  const [convertResults, setConvertResults] = useState<ConvertItemResult[]>([]);
  const [toast, setToast] = useState<AppleToast | null>(null);

  // Bounded LRU cache for full inspect payloads (prevents unbounded memory growth)
  const inspectCache = useRef<Map<string, ScanItem>>(new Map());

  const cacheInspectItem = useCallback((path: string, item: ScanItem) => {
    if (inspectCache.current.size >= MAX_INSPECT_CACHE) {
      const oldestKey = inspectCache.current.keys().next().value;
      if (oldestKey) {
        inspectCache.current.delete(oldestKey);
      }
    }
    inspectCache.current.set(path, item);
  }, []);

  const showToast = useCallback(
    (type: "success" | "error" | "info", title: string, message: string) => {
      const id = Date.now();
      setToast({ id, type, title, message });
      setTimeout(() => {
        setToast((prev) => (prev?.id === id ? null : prev));
      }, 4000);
    },
    []
  );

  useEffect(() => {
    let unlisten: (() => void) | undefined;
    onInjectorProgress((evt) => {
      setCurrentProgress(evt);
      if (evt.stage === "start") {
        setAmbientArtUrl(null);
      } else if (evt.cover_art_url) {
        setAmbientArtUrl(evt.cover_art_url);
      }
    }).then((fn) => {
      unlisten = fn;
    });

    return () => {
      if (unlisten) unlisten();
    };
  }, []);

  const handleInspect = useCallback(
    async (item: ScanItem) => {
      const cached = inspectCache.current.get(item.path);
      if (cached) {
        setInspectedItem(cached);
        setAmbientArtUrl(cached.cover_art_data_url ?? null);
        return;
      }
      try {
        const full = await runInspect(item.path, true);
        cacheInspectItem(item.path, full);
        setInspectedItem(full);
        setAmbientArtUrl(full.cover_art_data_url ?? null);
      } catch (e) {
        console.error("Inspect failed:", e);
        setInspectedItem(item);
        setAmbientArtUrl(null);
      }
    },
    [cacheInspectItem]
  );

  const inspectedIndex = useMemo(() => {
    if (!inspectedItem) return -1;
    return scannedItems.findIndex((i) => i.path === inspectedItem.path);
  }, [inspectedItem, scannedItems]);

  const handleNavigateInspect = useCallback(
    (direction: "prev" | "next") => {
      if (inspectedIndex === -1 || scannedItems.length === 0) return;
      const nextIndex =
        direction === "next"
          ? (inspectedIndex + 1) % scannedItems.length
          : (inspectedIndex - 1 + scannedItems.length) % scannedItems.length;
      handleInspect(scannedItems[nextIndex]);
    },
    [inspectedIndex, scannedItems, handleInspect]
  );

  const handleCloseInspect = useCallback(() => {
    setInspectedItem(null);
    if (activeTab === "inspect") {
      setActiveTab("scan");
    }
  }, [activeTab]);

  useEffect(() => {
    if (activeTab === "inspect" && !inspectedItem && scannedItems.length > 0) {
      const target =
        scannedItems.find((i) => selectedPaths.has(i.path)) || scannedItems[0];
      handleInspect(target);
    }
  }, [activeTab, inspectedItem, scannedItems, selectedPaths, handleInspect]);

  const handlePathsSelected = useCallback(
    async (paths: string[], append: boolean = false) => {
      if (!paths || paths.length === 0) return;
      setIsScanning(true);
      try {
        const res = await runScan(paths, recursiveScan, false);
        if (!append) inspectCache.current.clear();
        setScannedItems((prev) => {
          if (!append || prev.length === 0) {
            return res.items;
          }
          const existingMap = new Map(prev.map((item) => [item.path, item]));
          for (const item of res.items) {
            existingMap.set(item.path, item);
          }
          return Array.from(existingMap.values());
        });
        setActiveTab("scan");

        showToast(
          "success",
          "Library scanned",
          `Loaded ${res.items.length} audio track(s) (${res.incomplete} incomplete)`
        );

        const firstWithArt = res.items.find((i) => i.has_cover_art);
        if (firstWithArt) {
          runInspect(firstWithArt.path, true).then((full) => {
            if (full.cover_art_data_url) {
              setAmbientArtUrl(full.cover_art_data_url);
            }
          });
        }
      } catch (e) {
        console.error("Scanning failed:", e);
        showToast("error", "Scan failed", String(e));
      } finally {
        setIsScanning(false);
      }
    },
    [recursiveScan, showToast]
  );

  const handleToggleSelect = useCallback((path: string) => {
    setSelectedPaths((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }, []);

  const handleSelectMany = useCallback((paths: string[]) => {
    setSelectedPaths(new Set(paths));
  }, []);

  const handleClearSelection = useCallback(() => {
    setSelectedPaths(new Set());
  }, []);

  const handleQuickAddFiles = async () => {
    const files = await pickAudioFiles();
    if (files.length > 0) {
      await handlePathsSelected(files, true);
    }
  };

  const handleQuickAddFolder = async () => {
    const folder = await pickLibraryFolder();
    if (folder) {
      await handlePathsSelected([folder], true);
    }
  };

  const handleRescan = async () => {
    if (scannedItems.length === 0) return;
    const paths = scannedItems.map((i) => i.path);
    await handlePathsSelected(paths, false);
  };

  const handleClearLibrary = () => {
    inspectCache.current.clear();
    setScannedItems([]);
    setSelectedPaths(new Set());
    setInspectedItem(null);
    setAmbientArtUrl(null);
    setInjectResults([]);
    setConvertResults([]);
    showToast("info", "Library cleared", "Removed loaded tracks from session");
  };

  const handleStartInject = async (params: {
    paths: string[];
    threshold: number;
    dryRun: boolean;
    overwrite: boolean;
    convertWav: boolean;
  }) => {
    setIsInjecting(true);
    setCurrentProgress(null);
    try {
      const res = await runInject({
        paths: params.paths,
        threshold: params.threshold,
        dryRun: params.dryRun,
        overwrite: params.overwrite,
        convertWav: params.convertWav,
      });
      setInjectResults(res.items);

      showToast(
        "success",
        params.dryRun ? "Dry run complete" : "Metadata injected",
        `Processed ${res.processed} track(s) • ${res.success} succeeded`
      );

      if (scannedItems.length > 0) {
        const convertedMap = new Map<string, string>();
        for (const item of res.items) {
          if (item.file && item.file.toLowerCase().endsWith(".flac")) {
            const oldWav = item.file.replace(/\.flac$/i, ".wav");
            convertedMap.set(oldWav, item.file);
          }
        }
        const updatedPaths = scannedItems.map(
          (i) => convertedMap.get(i.path) || i.path
        );
        const refreshed = await runScan(
          Array.from(new Set(updatedPaths)),
          false,
          false
        );
        setScannedItems(refreshed.items);
      }
    } catch (e) {
      console.error("Injection error:", e);
      showToast("error", "Injection failed", String(e));
    } finally {
      setIsInjecting(false);
    }
  };

  const handleInjectSingle = async (item: ScanItem) => {
    setActiveTab("inject");
    await handleStartInject({
      paths: [item.path],
      threshold: 0.7,
      dryRun: false,
      overwrite: false,
      convertWav: true,
    });
  };

  const handleInjectBatch = (items: ScanItem[]) => {
    setActiveTab("inject");
    handleStartInject({
      paths: items.map((i) => i.path),
      threshold: 0.7,
      dryRun: false,
      overwrite: false,
      convertWav: true,
    });
  };

  const handleStartConvert = async (params: {
    paths: string[];
    outputDir?: string | null;
    inject: boolean;
    deleteOriginal: boolean;
    compressionLevel: number;
    threshold: number;
    dryRun: boolean;
  }) => {
    setIsConverting(true);
    setCurrentProgress(null);
    try {
      const res = await runConvert(params);
      setConvertResults(res.items);

      showToast(
        "success",
        "WAV encoding complete",
        `Converted ${res.converted} file(s) to lossless FLAC`
      );

      if (scannedItems.length > 0) {
        const conversionMap = new Map<string, string>();
        for (const c of res.items) {
          if (c.source && c.destination) {
            conversionMap.set(c.source, c.destination);
          }
        }
        const updatedPaths = scannedItems.map(
          (item) => conversionMap.get(item.path) || item.path
        );
        const refreshed = await runScan(
          Array.from(new Set(updatedPaths)),
          false,
          false
        );
        setScannedItems(refreshed.items);
      }
    } catch (e) {
      console.error("Conversion failed:", e);
      showToast("error", "Conversion failed", String(e));
    } finally {
      setIsConverting(false);
    }
  };

  const handleConvertSingle = (item: ScanItem) => {
    setActiveTab("convert");
    handleStartConvert({
      paths: [item.path],
      outputDir: null,
      inject: true,
      deleteOriginal: false,
      compressionLevel: 8,
      threshold: 0.7,
      dryRun: false,
    });
  };

  const handleConvertBatch = (items: ScanItem[]) => {
    setActiveTab("convert");
    handleStartConvert({
      paths: items.map((i) => i.path),
      outputDir: null,
      inject: true,
      deleteOriginal: false,
      compressionLevel: 8,
      threshold: 0.7,
      dryRun: false,
    });
  };

  // Single-pass computation for library statistics
  const { incompleteCount, wavCount } = useMemo(() => {
    let inc = 0;
    let wav = 0;
    for (const item of scannedItems) {
      if (item.is_incomplete) inc++;
      const fmt = item.audio_format.toLowerCase();
      if (fmt === "wav" || fmt === "wave" || fmt === "aiff" || fmt === "aif") {
        wav++;
      }
    }
    return { incompleteCount: inc, wavCount: wav };
  }, [scannedItems]);

  const viewMeta: Record<ActiveTab, { title: string; subtitle: string }> = {
    scan: {
      title: "Library",
      subtitle:
        scannedItems.length > 0
          ? `${scannedItems.length} tracks loaded • ${incompleteCount} awaiting metadata`
          : "Import FLAC, MP3, or uncompressed WAV masters",
    },
    inject: {
      title: "Waterfall Injector",
      subtitle:
        "Multi-provider acoustic resolution & 3000px master artwork embedding",
    },
    inspect: {
      title: "Track Inspector",
      subtitle:
        "Inspect Vorbis comments, ID3v2.4 frames, Chromaprint hashes & artwork",
    },
    convert: {
      title: "WAV to FLAC Studio",
      subtitle: "Bit-perfect FFmpeg lossless encoding with automatic tagging",
    },
    settings: {
      title: "Settings",
      subtitle: "Configure streaming credentials, acoustic lookup & thresholds",
    },
  };

  return (
    <div className="relative flex flex-col h-screen w-screen overflow-hidden bg-[#000000] text-[#F5F5F7] antialiased">
      {/* Optimized Ambient Artwork Atmosphere */}
      {ambientArtUrl && (
        <div
          className="ambient-glow"
          style={{ backgroundImage: `url(${ambientArtUrl})` }}
        />
      )}

      {/* Floating Apple Notification Toast */}
      <AnimatePresence>
        {toast && (
          <motion.div
            key={toast.id}
            initial={{ opacity: 0, y: -16, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -12, scale: 0.96 }}
            transition={{ type: "spring", duration: 0.3, bounce: 0 }}
            className="fixed top-14 left-1/2 -translate-x-1/2 z-50 flex items-center space-x-3 px-4 py-2.5 rounded-xl glass-panel shadow-2xl min-w-[320px] max-w-md border border-white/10"
          >
            {toast.type === "error" ? (
              <AlertCircle className="w-4 h-4 text-[#FF453A] shrink-0" />
            ) : (
              <CheckCircle2 className="w-4 h-4 text-[#34C759] shrink-0" />
            )}
            <div className="flex-1 text-xs">
              <div className="font-semibold text-[#F5F5F7]">{toast.title}</div>
              <div className="text-[#A1A1A6] truncate">{toast.message}</div>
            </div>
            <button
              type="button"
              onClick={() => setToast(null)}
              className="p-1 rounded-md text-[#A1A1A6] hover:text-[#F5F5F7] hover:bg-white/10 transition-colors"
              title="Dismiss notification"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Frameless Toolbar */}
      <Titlebar />

      {/* Main Split View Workspace */}
      <div className="flex flex-1 overflow-hidden relative z-10">
        <Sidebar
          activeTab={activeTab}
          onTabChange={setActiveTab}
          scannedCount={scannedItems.length}
          incompleteCount={incompleteCount}
          wavCount={wavCount}
        />

        <main className="flex-1 flex flex-col px-6 py-4 overflow-hidden">
          {/* Header Bar */}
          <div className="flex items-center justify-between pb-3.5 mb-3.5 border-b border-white/[0.08] shrink-0">
            <div>
              <h1 className="text-xl display-heading text-[#F5F5F7]">
                {viewMeta[activeTab].title}
              </h1>
              <p className="text-xs text-[#A1A1A6] mt-0.5 tabular-nums">
                {viewMeta[activeTab].subtitle}
              </p>
            </div>

            <div className="flex items-center space-x-2">
              <button
                type="button"
                onClick={() => setRecursiveScan(!recursiveScan)}
                title="Toggle recursive subfolder scanning"
                className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                  recursiveScan
                    ? "bg-[#0A84FF]/15 text-[#0A84FF] border-[#0A84FF]/35"
                    : "bg-white/[0.04] text-[#A1A1A6] border-white/[0.08]"
                }`}
              >
                Recursive: {recursiveScan ? "On" : "Off"}
              </button>

              {scannedItems.length > 0 && (
                <>
                  <button
                    type="button"
                    onClick={handleRescan}
                    disabled={isScanning}
                    title="Rescan current library tracks"
                    className="apple-btn-secondary flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-[#F5F5F7]"
                  >
                    <RefreshCw
                      className={`w-3.5 h-3.5 text-[#34C759] ${
                        isScanning ? "animate-spin" : ""
                      }`}
                    />
                    <span>Rescan</span>
                  </button>
                  <button
                    type="button"
                    onClick={handleQuickAddFiles}
                    disabled={isScanning}
                    className="apple-btn-secondary flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-[#F5F5F7]"
                  >
                    <Plus className="w-3.5 h-3.5 text-[#0A84FF]" />
                    <span>Add tracks</span>
                  </button>
                  <button
                    type="button"
                    onClick={handleQuickAddFolder}
                    disabled={isScanning}
                    className="apple-btn-secondary flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-[#F5F5F7]"
                  >
                    <FolderPlus className="w-3.5 h-3.5 text-[#0A84FF]" />
                    <span>Add folder</span>
                  </button>
                  <button
                    type="button"
                    onClick={handleClearLibrary}
                    disabled={isScanning}
                    title="Clear library list"
                    className="apple-btn-secondary flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-[#A1A1A6] hover:text-[#FF453A]"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Active Workspace View */}
          {scannedItems.length === 0 && activeTab === "scan" ? (
            <div className="flex-1 flex items-center justify-center max-w-xl mx-auto w-full">
              <DropZone
                onPathsSelected={handlePathsSelected}
                isScanning={isScanning}
              />
            </div>
          ) : (
            <div className="flex-1 overflow-hidden">
              {(activeTab === "scan" || activeTab === "inspect") &&
                (scannedItems.length > 0 ? (
                  <ScanView
                    items={scannedItems}
                    selectedPaths={selectedPaths}
                    onToggleSelect={handleToggleSelect}
                    onSelectMany={handleSelectMany}
                    onClearSelection={handleClearSelection}
                    onInspect={handleInspect}
                    onInjectSingle={handleInjectSingle}
                    onInjectBatch={handleInjectBatch}
                    onConvertSingle={handleConvertSingle}
                    onConvertBatch={handleConvertBatch}
                  />
                ) : (
                  <div className="flex-1 flex items-center justify-center max-w-xl mx-auto w-full h-full">
                    <DropZone
                      onPathsSelected={handlePathsSelected}
                      isScanning={isScanning}
                    />
                  </div>
                ))}

              {activeTab === "inject" && (
                <InjectView
                  items={scannedItems}
                  isInjecting={isInjecting}
                  currentProgress={currentProgress}
                  lastResults={injectResults}
                  onStartInject={handleStartInject}
                />
              )}

              {activeTab === "convert" && (
                <ConvertView
                  items={scannedItems}
                  isConverting={isConverting}
                  currentProgress={currentProgress}
                  lastResults={convertResults}
                  onStartConvert={handleStartConvert}
                />
              )}

              {activeTab === "settings" && (
                <SettingsModal
                  onSaved={() =>
                    showToast(
                      "success",
                      "Settings saved",
                      "Configuration updated on disk"
                    )
                  }
                />
              )}
            </div>
          )}
        </main>
      </div>

      {/* Floating Track Inspector Sheet */}
      <InspectDrawer
        item={inspectedItem}
        currentIndex={inspectedIndex >= 0 ? inspectedIndex : 0}
        totalCount={scannedItems.length}
        onClose={handleCloseInspect}
        onNavigate={handleNavigateInspect}
        onInject={(item) => {
          handleCloseInspect();
          handleInjectSingle(item);
        }}
      />
    </div>
  );
};
