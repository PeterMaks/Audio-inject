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

// WebSocket RPC Bridge for Web Browser clients
let socket: WebSocket | null = null;
let socketPromise: Promise<WebSocket> | null = null;
const pendingRequests = new Map<
  string,
  { resolve: (val: any) => void; reject: (err: any) => void }
>();
const progressListeners = new Set<(event: ProgressEvent) => void>();

const getWebSocket = (): Promise<WebSocket> => {
  if (socket && socket.readyState === WebSocket.OPEN) {
    return Promise.resolve(socket);
  }
  if (socketPromise) {
    return socketPromise;
  }

  socketPromise = new Promise((resolve, reject) => {
    const wsUrl = "ws://127.0.0.1:8765";
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      socket = ws;
      socketPromise = null;
      resolve(ws);
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "event" && msg.event === "injector-progress") {
          for (const listener of progressListeners) {
            listener(msg.payload);
          }
          return;
        }

        if (msg.id && pendingRequests.has(msg.id)) {
          const { resolve: reqResolve, reject: reqReject } = pendingRequests.get(msg.id)!;
          pendingRequests.delete(msg.id);
          if (msg.error) {
            reqReject(new Error(msg.error));
          } else {
            reqResolve(msg.result);
          }
        }
      } catch (err) {
        console.warn("WebSocket parse error:", err);
      }
    };

    ws.onerror = (err) => {
      socket = null;
      socketPromise = null;
      console.warn("WebSocket connection error. Ensure the backend server is running (`flac-meta-injector serve`).", err);
      reject(err);
    };

    ws.onclose = () => {
      socket = null;
      socketPromise = null;
    };
  });

  return socketPromise;
};

// Universal Command Invoker
async function executeCommand<T>(action: string, params: Record<string, any> = {}): Promise<T> {
  if (isTauriEnvironment()) {
    return await invoke<T>(action, params);
  }

  try {
    const ws = await getWebSocket();
    const id = Math.random().toString(36).substring(2, 10);
    return await new Promise<T>((resolve, reject) => {
      pendingRequests.set(id, { resolve, reject });
      ws.send(JSON.stringify({ id, action, params }));
    });
  } catch (err) {
    console.error(`WebSocket RPC failed for action '${action}':`, err);
    throw err;
  }
}

export const checkSystemHealth = async (): Promise<HealthStatus> => {
  if (isTauriEnvironment()) {
    return await invoke<HealthStatus>("check_system_health");
  }
  try {
    return await executeCommand<HealthStatus>("check_system_health");
  } catch {
    return {
      python_version: "Offline",
      in_venv: false,
      ffmpeg: { available: false, path: null },
      fpcalc: { available: false, path: null },
      env_status: {
        acoustid_configured: false,
        spotify_configured: false,
        confidence_threshold: 0.7,
        cover_art_min_resolution: 600,
        rate_limit_delay: 1.0,
        request_timeout: 15.0,
      },
    };
  }
};

export const runScan = async (
  paths: string[],
  recursive: boolean = true,
  onlyIncomplete: boolean = false
): Promise<ScanResponse> => {
  return await executeCommand<ScanResponse>("run_scan", {
    paths,
    recursive,
    onlyIncomplete,
  });
};

export const runInspect = async (
  path: string,
  includeArtBase64: boolean = true
): Promise<ScanItem> => {
  return await executeCommand<ScanItem>("run_inspect", {
    path,
    includeArtBase64,
  });
};

export const runFingerprint = async (path: string): Promise<FingerprintResponse> => {
  return await executeCommand<FingerprintResponse>("run_fingerprint", { path });
};

export const runInject = async (params: {
  paths: string[];
  dryRun?: boolean;
  threshold?: number;
  overwrite?: boolean;
  convertWav?: boolean;
  recursive?: boolean;
  songLink?: string;
}): Promise<InjectResponse> => {
  return await executeCommand<InjectResponse>("run_inject", {
    paths: params.paths,
    dryRun: params.dryRun ?? false,
    threshold: params.threshold ?? 0.7,
    overwrite: params.overwrite ?? false,
    convertWav: params.convertWav ?? true,
    recursive: params.recursive ?? true,
    songLink: params.songLink,
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
  return await executeCommand<ConvertResponse>("run_convert", {
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
  return await executeCommand<EnvSettings>("get_settings");
};

export const saveSettings = async (settings: Partial<EnvSettings>): Promise<EnvSettings> => {
  return await executeCommand<EnvSettings>("save_settings", { settings });
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
  if (isTauriEnvironment()) {
    return await listen<ProgressEvent>("injector-progress", (event) => {
      callback(event.payload);
    });
  }

  // Web WebSocket progress listener
  progressListeners.add(callback);
  getWebSocket().catch(() => {});
  return () => {
    progressListeners.delete(callback);
  };
};

export const pickAudioFiles = async (): Promise<string[]> => {
  if (isTauriEnvironment()) {
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
      if (!selected) return [];
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
  }

  // Web browser fallback
  const input = window.prompt(
    "Enter audio file path(s) on host machine (comma-separated):",
    "tests/fixtures/sample.flac"
  );
  if (!input || !input.trim()) return [];
  return input
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
};

export const pickLibraryFolder = async (): Promise<string | null> => {
  if (isTauriEnvironment()) {
    try {
      const { open } = await import("@tauri-apps/plugin-dialog");
      const selected = await open({
        directory: true,
        multiple: false,
      });
      if (!selected) return null;
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
  }

  // Web browser fallback
  const folder = window.prompt(
    "Enter library folder path on host machine (e.g. tests/fixtures or C:\\Music):",
    "tests/fixtures"
  );
  return folder && folder.trim() ? folder.trim() : null;
};
