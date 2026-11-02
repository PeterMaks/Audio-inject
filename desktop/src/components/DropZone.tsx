import React, { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
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

  useEffect(() => {
    if (!isTauriEnvironment()) return;
    let isMounted = true;
    let unlisten: (() => void) | undefined;

    import("@tauri-apps/api/webviewWindow")
      .then(({ getCurrentWebviewWindow }) => {
        if (!isMounted) return;
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
        if (!isMounted) {
          if (fn) fn();
        } else {
          unlisten = fn;
        }
      })
      .catch((err) => console.warn("Tauri drag-drop listener skipped:", err));

    return () => {
      isMounted = false;
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
      console.warn("pickAudioFiles error:", err);
    }
    if (!isTauriEnvironment()) {
      fileInputRef.current?.click();
    }
  };

  const handleSelectDirectory = async () => {
    try {
      const folderPath = await pickLibraryFolder();
      if (folderPath) {
        onPathsSelected([folderPath]);
        return;
      }
    } catch (err) {
      console.warn("pickLibraryFolder error:", err);
    }
    if (!isTauriEnvironment()) {
      folderInputRef.current?.click();
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const paths: string[] = [];
      for (let i = 0; i < e.target.files.length; i++) {
        const file = e.target.files[i] as any;
        if (file.path) paths.push(file.path);
      }
      if (paths.length > 0) onPathsSelected(paths);
    }
  };

  return (
    <motion.div
      animate={{
        scale: isDragOver ? 1.01 : 1,
        borderColor: isDragOver
          ? "rgba(10, 132, 255, 0.7)"
          : "rgba(255, 255, 255, 0.08)",
      }}
      transition={{ type: "spring", duration: 0.25, bounce: 0 }}
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragOver(true);
      }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setIsDragOver(false);
        if (isTauriEnvironment()) return;
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
          const paths: string[] = [];
          for (let i = 0; i < e.dataTransfer.files.length; i++) {
            const file = e.dataTransfer.files[i] as any;
            if (file.path) paths.push(file.path);
          }
          if (paths.length > 0) onPathsSelected(paths);
        }
      }}
      className={`relative w-full rounded-2xl p-8 flex flex-col items-center justify-center text-center glass-panel ${
        isDragOver ? "bg-[#0A84FF]/10" : ""
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

      {/* Concentric Icon Tile: Outer rounded-2xl (24px) p-8 (32px), Inner rounded-xl (12px) */}
      <div className="w-14 h-14 rounded-xl surface-elevated flex items-center justify-center mb-4 shadow-md">
        <UploadCloud
          className={`w-6 h-6 transition-transform duration-150 ${
            isDragOver ? "text-[#0A84FF] scale-105" : "text-[#F5F5F7]"
          }`}
        />
      </div>

      <h3 className="text-base display-heading text-[#F5F5F7]">
        {isScanning ? "Scanning audio masters…" : "Drop audio files or folders"}
      </h3>
      <p className="text-xs text-[#A1A1A6] mt-1 max-w-[44ch] leading-relaxed">
        Drag FLAC, MP3, or uncompressed WAV masters from Explorer to inspect
        headers, verify acoustic fingerprints, and embed artwork.
      </p>

      <div className="flex items-center space-x-3 mt-5">
        <button
          type="button"
          onClick={handleSelectFiles}
          disabled={isScanning}
          className="apple-btn-secondary flex items-center space-x-2 px-4 py-2 rounded-lg text-xs font-medium text-[#F5F5F7] disabled:opacity-50 cursor-pointer"
        >
          <FileAudio className="w-3.5 h-3.5 text-[#0A84FF]" />
          <span>Choose files…</span>
        </button>

        <button
          type="button"
          onClick={handleSelectDirectory}
          disabled={isScanning}
          className="apple-btn-primary flex items-center space-x-2 px-4 py-2 rounded-lg text-xs font-semibold text-white disabled:opacity-50 cursor-pointer"
        >
          <FolderOpen className="w-3.5 h-3.5" />
          <span>Select library folder…</span>
        </button>
      </div>
    </motion.div>
  );
};
