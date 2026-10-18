import React, { useEffect, useRef, useState } from "react";
import { UploadCloud, FolderOpen, FileAudio } from "lucide-react";
import {
  isTauriEnvironment,
  pickAudioFiles,
  pickLibraryFolder,
} from "../lib/tauriClient";

interface DropZoneProps {
  onPathsSelected: (paths: string[]) => void;
  isScanning?: boolean;
}

export const DropZone: React.FC<DropZoneProps> = ({
  onPathsSelected,
  isScanning = false,
}) => {
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);

  // Subscribe to native Tauri v2 OS drag-drop events for reliable Windows paths
  useEffect(() => {
    if (!isTauriEnvironment()) return;
    let unlisten: (() => void) | undefined;

    import("@tauri-apps/api/webviewWindow")
      .then(({ getCurrentWebviewWindow }) => {
        const win = getCurrentWebviewWindow();
        return win.onDragDropEvent((event) => {
          if (event.payload.type === "over") {
            setIsDragOver(true);
          } else if (event.payload.type === "leave") {
            setIsDragOver(false);
          } else if (event.payload.type === "drop") {
            setIsDragOver(false);
            if (event.payload.paths && event.payload.paths.length > 0) {
              onPathsSelected(event.payload.paths);
            }
          }
        });
      })
      .then((fn) => {
        unlisten = fn;
      })
      .catch((err) => console.warn("Tauri drag-drop listener skipped:", err));

    return () => {
      if (unlisten) unlisten();
    };
  }, [onPathsSelected]);

  const handleSelectFiles = async () => {
    try {
      const paths = await pickAudioFiles();
      if (paths && paths.length > 0) {
        onPathsSelected(paths);
        return;
      }
    } catch (err) {
      console.warn("pickAudioFiles fallback:", err);
    }
    fileInputRef.current?.click();
  };

  const handleSelectDirectory = async () => {
    try {
      const folderPath = await pickLibraryFolder();
      if (folderPath) {
        onPathsSelected([folderPath]);
        return;
      }
    } catch (err) {
      console.warn("pickLibraryFolder fallback:", err);
    }
    folderInputRef.current?.click();
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const paths: string[] = [];
      for (let i = 0; i < e.target.files.length; i++) {
        const file = e.target.files[i] as any;
        if (file.path) paths.push(file.path);
        else if (file.name) paths.push(file.name);
      }
      if (paths.length > 0) onPathsSelected(paths);
    }
  };

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragOver(true);
      }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setIsDragOver(false);
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
          const paths: string[] = [];
          for (let i = 0; i < e.dataTransfer.files.length; i++) {
            const file = e.dataTransfer.files[i] as any;
            if (file.path) paths.push(file.path);
          }
          if (paths.length > 0) onPathsSelected(paths);
        }
      }}
      className={`relative w-full rounded-3xl p-10 transition-all duration-300 flex flex-col items-center justify-center text-center glass-panel ${isDragOver
          ? "border-[#0A84FF] bg-[#0A84FF]/10 scale-[1.01]"
          : "hover:border-white/20"
        }`}
    >
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileInputChange}
        multiple
        accept=".flac,.mp3,.wav,.wave,.aiff,.aif"
        className="hidden"
      />
      <input
        type="file"
        ref={folderInputRef}
        onChange={handleFileInputChange}
        {...({ webkitdirectory: "", directory: "" } as any)}
        className="hidden"
      />

      <div className="w-16 h-16 rounded-2xl bg-gradient-to-b from-white/[0.12] to-white/[0.04] border border-white/[0.14] flex items-center justify-center mb-5 shadow-lg">
        <UploadCloud
          className={`w-7 h-7 transition-transform duration-200 ${isDragOver ? "text-[#0A84FF] scale-110" : "text-white/80"
            }`}
        />
      </div>

      <h3 className="text-base font-semibold tracking-tight text-white">
        {isScanning ? "Scanning Audio Masters…" : "Drop Audio Files or Folders"}
      </h3>
      <p className="text-xs text-white/50 mt-1.5 max-w-sm leading-relaxed">
        Drag FLAC, MP3, or uncompressed WAV files from Explorer to inspect
        headers and embed 3000px master artwork.
      </p>

      <div className="flex items-center space-x-3 mt-6">
        <button
          onClick={handleSelectFiles}
          disabled={isScanning}
          className="apple-btn-secondary flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-medium text-white disabled:opacity-50 cursor-pointer"
        >
          <FileAudio className="w-4 h-4 text-[#0A84FF]" />
          <span>Choose Files…</span>
        </button>

        <button
          onClick={handleSelectDirectory}
          disabled={isScanning}
          className="apple-btn-primary flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-semibold text-white disabled:opacity-50 cursor-pointer"
        >
          <FolderOpen className="w-4 h-4" />
          <span>Select Library Folder…</span>
        </button>
      </div>
    </div>
  );
};