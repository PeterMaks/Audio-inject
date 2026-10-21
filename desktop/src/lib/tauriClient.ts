import { invoke } from "@tauri-apps/api/core";
import { listen, UnlistenFn } from "@tauri-apps/api/event";
import {
  ConvertResponse,
  EnvSettings,
  FingerprintResponse,
  HealthStatus,
  InjectResponse,
  ProgressEvent,
  ScanItem,
  ScanResponse,
} from "../types/injector";

// Detect if running inside a Tauri WebView window
export const isTauriEnvironment = (): boolean => {
  return typeof window !== "undefined" && Boolean((window as any).__TAURI_INTERNALS__);
};

export const checkSystemHealth = async (): Promise<HealthStatus> => {
  if (!isTauriEnvironment()) {
    return {
      python_version: "3.13.4 (Dev Mock)",
      in_venv: true,
      ffmpeg: { available: true, path: "C:\\ffmpeg\\bin\\ffmpeg.exe" },
      fpcalc: { available: true, path: "C:\\fpcalc\\bin\\fpcalc.exe" },
      env_status: {
        acoustid_configured: true,
        spotify_configured: false,
        confidence_threshold: 0.7,
        cover_art_min_resolution: 600,
        rate_limit_delay: 1.0,
        request_timeout: 15.0,
      },
    };
  }
  return await invoke<HealthStatus>("check_system_health");
};

export const runScan = async (
  paths: string[],
  recursive: boolean = true,
  onlyIncomplete: boolean = false
): Promise<ScanResponse> => {
  if (!isTauriEnvironment()) {
    console.warn("runScan called outside Tauri environment");
    return {
      items: [],
      total: 0,
      incomplete: 0,
      complete: 0,
      format_counts: {},
    };
  }
  return await invoke<ScanResponse>("run_scan", {
    paths,
    recursive,
    onlyIncomplete,
  });
};

export const runInspect = async (
  path: string,
  includeArtBase64: boolean = true
): Promise<ScanItem> => {
  return await invoke<ScanItem>("run_inspect", {
    path,
    includeArtBase64,
  });
};

export const runFingerprint = async (path: string): Promise<FingerprintResponse> => {
  return await invoke<FingerprintResponse>("run_fingerprint", { path });
};

export const runInject = async (params: {
  paths: string[];
  dryRun?: boolean;
  threshold?: number;
  overwrite?: boolean;
  convertWav?: boolean;
  recursive?: boolean;
}): Promise<InjectResponse> => {
  return await invoke<InjectResponse>("run_inject", {
    paths: params.paths,
    dryRun: params.dryRun ?? false,
    threshold: params.threshold ?? 0.7,
    overwrite: params.overwrite ?? false,
    convertWav: params.convertWav ?? true,
    recursive: params.recursive ?? true,
  });
};

export const runConvert = async (params: {
  paths: string[];
  outputDir?: string | null;
  inject?: boolean;
  deleteOriginal?: boolean;
  compressionLevel?: number;
  threshold?: number;
  dryRun?: boolean;
}): Promise<ConvertResponse> => {
  return await invoke<ConvertResponse>("run_convert", {
    paths: params.paths,
    outputDir: params.outputDir ?? null,
    inject: params.inject ?? true,
    deleteOriginal: params.deleteOriginal ?? false,
    compressionLevel: params.compressionLevel ?? 8,
    threshold: params.threshold ?? 0.7,
    dryRun: params.dryRun ?? false,
  });
};

export const getSettings = async (): Promise<EnvSettings> => {
  return await invoke<EnvSettings>("get_settings");
};

export const saveSettings = async (settings: Partial<EnvSettings>): Promise<EnvSettings> => {
  return await invoke<EnvSettings>("save_settings", { settings });
};

export const minimizeWindow = async (): Promise<void> => {
  if (isTauriEnvironment()) {
    await invoke("minimize_window");
  }
};

export const maximizeWindow = async (): Promise<void> => {
  if (isTauriEnvironment()) {
    await invoke("maximize_window");
  }
};

export const closeWindow = async (): Promise<void> => {
  if (isTauriEnvironment()) {
    await invoke("close_window");
  }
};

export const onInjectorProgress = async (
  callback: (event: ProgressEvent) => void
): Promise<UnlistenFn> => {
  if (!isTauriEnvironment()) {
    return () => {};
  }
  return await listen<ProgressEvent>("injector-progress", (event) => {
    callback(event.payload);
  });
};

export const pickAudioFiles = async (): Promise<string[]> => {
  if (!isTauriEnvironment()) {
    return [];
  }
  try {
    const { open } = await import("@tauri-apps/plugin-dialog");
    const selected = await open({
      multiple: true,
      directory: false,
      filters: [
        {
          name: "Supported Audio Files",
          extensions: ["flac", "mp3", "wav", "wave", "aiff", "aif"],
        },
      ],
    });
    if (!selected) {
      return [];
    }
    return Array.isArray(selected) ? selected : [selected];
  } catch (err) {
    console.warn("Plugin dialog open error, fallback to invoke:", err);
    try {
      const res = await invoke<string[]>("pick_audio_files");
      return res || [];
    } catch (invokeErr) {
      console.error("invoke pick_audio_files error:", invokeErr);
      return [];
    }
  }
};

export const pickLibraryFolder = async (): Promise<string | null> => {
  if (!isTauriEnvironment()) {
    return null;
  }
  try {
    const { open } = await import("@tauri-apps/plugin-dialog");
    const selected = await open({
      directory: true,
      multiple: false,
    });
    if (!selected) {
      return null;
    }
    return typeof selected === "string" ? selected : null;
  } catch (err) {
    console.warn("Plugin dialog open folder error, fallback to invoke:", err);
    try {
      const res = await invoke<string | null>("pick_library_folder");
      return res || null;
    } catch (invokeErr) {
      console.error("invoke pick_library_folder error:", invokeErr);
      return null;
    }
  }
};
