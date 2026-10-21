import React, { useState, useEffect, useCallback } from "react";
import { Plus, FolderPlus, CheckCircle2, AlertCircle, X, RefreshCw, Trash2 } from "lucide-react";
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

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<ActiveTab>("scan");
  const [scannedItems, setScannedItems] = useState<ScanItem[]>([]);
  const [inspectedItem, setInspectedItem] = useState<ScanItem | null>(null);
  const [ambientArtUrl, setAmbientArtUrl] = useState<string | null>(null);

  const [isScanning, setIsScanning] = useState<boolean>(false);
  const [isInjecting, setIsInjecting] = useState<boolean>(false);
  const [isConverting, setIsConverting] = useState<boolean>(false);

  const [currentProgress, setCurrentProgress] = useState<ProgressEvent | null>(
    null
  );
  const [injectResults, setInjectResults] = useState<InjectItemResult[]>([]);
  const [convertResults, setConvertResults] = useState<ConvertItemResult[]>([]);
  const [toast, setToast] = useState<AppleToast | null>(null);

  const showToast = useCallback(
    (type: "success" | "error" | "info", title: string, message: string) => {
      const id = Date.now();
      setToast({ id, type, title, message });
      setTimeout(() => {
        setToast((prev) => (prev?.id === id ? null : prev));
      }, 4200);
    },
    []
  );

  // Listen to live stream progress from Tauri Rust backend
  useEffect(() => {
    let unlisten: (() => void) | undefined;
    onInjectorProgress((evt) => {
      setCurrentProgress(evt);
      if (evt.cover_art_url) {
        setAmbientArtUrl(evt.cover_art_url);
      }
    }).then((fn) => {
      unlisten = fn;
    });

    return () => {
      if (unlisten) unlisten();
    };
  }, []);

  // Inspect track in detail
  const handleInspect = useCallback(async (item: ScanItem) => {
    try {
      const full = await runInspect(item.path, true);
      setInspectedItem(full);
      if (full.cover_art_data_url) {
        setAmbientArtUrl(full.cover_art_data_url);
      }
    } catch (e) {
      console.error("Inspect failed:", e);
      setInspectedItem(item);
    }
  }, []);

  // Auto-inspect first track when clicking Track Inspector tab if none selected
  useEffect(() => {
    if (activeTab === "inspect" && !inspectedItem && scannedItems.length > 0) {
      handleInspect(scannedItems[0]);
    }
  }, [activeTab, inspectedItem, scannedItems, handleInspect]);

  // Handle Drag & Drop or File Selection with merging support
  const handlePathsSelected = useCallback(
    async (paths: string[], append: boolean = false) => {
      if (!paths || paths.length === 0) return;
      setIsScanning(true);
      try {
        const res = await runScan(paths, true, false);
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
          "Library Scanned",
          `Loaded ${res.items.length} audio track(s) (${res.incomplete} incomplete).`
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
        showToast("error", "Scan Failed", String(e));
      } finally {
        setIsScanning(false);
      }
    },
    [showToast]
  );

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
    setScannedItems([]);
    setInspectedItem(null);
    setAmbientArtUrl(null);
    setInjectResults([]);
    setConvertResults([]);
    showToast("info", "Library Cleared", "Removed loaded tracks from session.");
  };

  // Start Waterfall Inject
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
        params.dryRun ? "Dry Run Complete" : "Metadata Injected",
        `Processed ${res.processed} track(s) • ${res.success} succeeded.`
      );

      if (scannedItems.length > 0) {
        // Map converted WAV to new FLAC paths
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
      showToast("error", "Injection Failed", String(e));
    } finally {
      setIsInjecting(false);
    }
  };

  // Single file injection
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

  // Batch injection
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

  // Start WAV conversion
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
        "WAV Encoding Complete",
        `Converted ${res.converted} file(s) to lossless FLAC.`
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
      showToast("error", "Conversion Failed", String(e));
    } finally {
      setIsConverting(false);
    }
  };

  // Single file WAV convert
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

  const incompleteCount = scannedItems.filter((i) => i.is_incomplete).length;

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
      subtitle: "Select any track to inspect Vorbis comments, ID3v2.4 frames & art",
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
    <div className="relative flex flex-col h-screen w-screen overflow-hidden bg-[#0c0c0f]/75 text-white antialiased">
      {/* Apple Music Dynamic Artwork Mesh */}
      {ambientArtUrl && (
        <div
          className="ambient-glow"
          style={{ backgroundImage: `url(${ambientArtUrl})` }}
        />
      )}

      {/* Floating Apple Notification Banner */}
      {toast && (
        <div className="fixed top-14 left-1/2 -translate-x-1/2 z-50 flex items-center space-x-3 px-4 py-2.5 rounded-2xl glass-panel border border-white/[0.18] shadow-2xl min-w-[320px] max-w-md animate-fade-in">
          {toast.type === "error" ? (
            <AlertCircle className="w-4 h-4 text-[#FF453A] shrink-0" />
          ) : (
            <CheckCircle2 className="w-4 h-4 text-[#30D158] shrink-0" />
          )}
          <div className="flex-1 text-xs">
            <div className="font-semibold text-white">{toast.title}</div>
            <div className="text-white/65 truncate">{toast.message}</div>
          </div>
          <button
            onClick={() => setToast(null)}
            className="p-1 rounded-full text-white/40 hover:text-white hover:bg-white/10 transition-colors"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Unified Frameless Toolbar */}
      <Titlebar />

      {/* Main Split View Workspace */}
      <div className="flex flex-1 overflow-hidden relative z-10">
        <Sidebar
          activeTab={activeTab}
          onTabChange={setActiveTab}
          scannedCount={scannedItems.length}
          incompleteCount={incompleteCount}
        />

        <main className="flex-1 flex flex-col px-7 py-5 overflow-hidden">
          {/* Apple HIG Large Title Header Bar */}
          <div className="flex items-center justify-between pb-4 mb-4 border-b border-white/[0.07] shrink-0">
            <div>
              <h1 className="text-xl font-semibold tracking-tight text-white">
                {viewMeta[activeTab].title}
              </h1>
              <p className="text-xs text-white/50 mt-0.5">
                {viewMeta[activeTab].subtitle}
              </p>
            </div>

            {scannedItems.length > 0 && (
              <div className="flex items-center space-x-2">
                <button
                  onClick={handleRescan}
                  disabled={isScanning}
                  title="Rescan current library tracks"
                  className="apple-btn-secondary flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-white/90"
                >
                  <RefreshCw
                    className={`w-3.5 h-3.5 text-[#30D158] ${
                      isScanning ? "animate-spin" : ""
                    }`}
                  />
                  <span>Rescan</span>
                </button>
                <button
                  onClick={handleQuickAddFiles}
                  disabled={isScanning}
                  className="apple-btn-secondary flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-white/90"
                >
                  <Plus className="w-3.5 h-3.5 text-[#0A84FF]" />
                  <span>Add Tracks</span>
                </button>
                <button
                  onClick={handleQuickAddFolder}
                  disabled={isScanning}
                  className="apple-btn-secondary flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-white/90"
                >
                  <FolderPlus className="w-3.5 h-3.5 text-[#0A84FF]" />
                  <span>Add Folder</span>
                </button>
                <button
                  onClick={handleClearLibrary}
                  disabled={isScanning}
                  title="Clear library list"
                  className="apple-btn-secondary flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-white/70 hover:text-[#FF453A]"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
          </div>

          {/* Active Workspace Body */}
          {scannedItems.length === 0 && activeTab === "scan" ? (
            <div className="flex-1 flex items-center justify-center max-w-xl mx-auto w-full">
              <DropZone
                onPathsSelected={handlePathsSelected}
                isScanning={isScanning}
              />
            </div>
          ) : (
            <div className="flex-1 overflow-hidden">
              {activeTab === "scan" && (
                <ScanView
                  items={scannedItems}
                  onInspect={handleInspect}
                  onInjectSingle={handleInjectSingle}
                  onInjectBatch={handleInjectBatch}
                  onConvertSingle={handleConvertSingle}
                />
              )}

              {activeTab === "inject" && (
                <InjectView
                  items={scannedItems}
                  isInjecting={isInjecting}
                  currentProgress={currentProgress}
                  lastResults={injectResults}
                  onStartInject={handleStartInject}
                />
              )}

              {activeTab === "inspect" && (
                <div className="flex flex-col h-full">
                  {scannedItems.length > 0 ? (
                    <ScanView
                      items={scannedItems}
                      onInspect={handleInspect}
                      onInjectSingle={handleInjectSingle}
                      onInjectBatch={handleInjectBatch}
                      onConvertSingle={handleConvertSingle}
                    />
                  ) : (
                    <div className="flex-1 flex items-center justify-center max-w-xl mx-auto w-full">
                      <DropZone
                        onPathsSelected={handlePathsSelected}
                        isScanning={isScanning}
                      />
                    </div>
                  )}
                </div>
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
                      "Configuration Saved",
                      "Updated .env settings on disk."
                    )
                  }
                />
              )}
            </div>
          )}
        </main>
      </div>

      {/* visionOS / Apple Music Floating Inspector Sheet */}
      <InspectDrawer
        item={inspectedItem}
        onClose={() => setInspectedItem(null)}
        onInject={(item) => {
          setInspectedItem(null);
          handleInjectSingle(item);
        }}
      />
    </div>
  );
};