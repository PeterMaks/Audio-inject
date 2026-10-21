use std::path::{Path, PathBuf};
use std::process::Stdio;
use serde_json::{json, Value};
use tauri::{AppHandle, Emitter, Manager, Window};
use tauri_plugin_dialog::DialogExt;
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command;

#[cfg(target_os = "windows")]
use window_vibrancy::{apply_acrylic, apply_mica};

/// Helper to locate the root workspace directory containing pyproject.toml
fn find_workspace_root() -> PathBuf {
    // 1. Check CARGO_MANIFEST_DIR ancestors (active in `cargo` / `tauri dev`)
    if let Ok(manifest) = std::env::var("CARGO_MANIFEST_DIR") {
        let mut curr = PathBuf::from(manifest);
        for _ in 0..5 {
            if curr.join("pyproject.toml").exists() && curr.join("src").exists() {
                return curr;
            }
            if let Some(parent) = curr.parent() {
                curr = parent.to_path_buf();
            } else {
                break;
            }
        }
    }

    // 2. Check current working directory ancestors
    let mut current = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    for _ in 0..5 {
        if current.join("pyproject.toml").exists() && current.join("src").exists() {
            return current;
        }
        if let Some(parent) = current.parent() {
            current = parent.to_path_buf();
        } else {
            break;
        }
    }
    // Fallback to parent of current directory
    PathBuf::from("..")
}

/// Helper to find Python executable in virtualenv or PATH
fn find_python_executable(root: &Path) -> PathBuf {
    #[cfg(target_os = "windows")]
    {
        let venv_py = root.join(".venv").join("Scripts").join("python.exe");
        if venv_py.exists() {
            return venv_py;
        }
    }

    #[cfg(not(target_os = "windows"))]
    {
        let venv_py = root.join(".venv").join("bin").join("python");
        if venv_py.exists() {
            return venv_py;
        }
    }

    if let Ok(venv_env) = std::env::var("VIRTUAL_ENV") {
        #[cfg(target_os = "windows")]
        let venv_py = PathBuf::from(&venv_env).join("Scripts").join("python.exe");
        #[cfg(not(target_os = "windows"))]
        let venv_py = PathBuf::from(&venv_env).join("bin").join("python");
        if venv_py.exists() {
            return venv_py;
        }
    }

    PathBuf::from("python")
}

#[cfg(target_os = "windows")]
const CREATE_NO_WINDOW: u32 = 0x08000000;

fn resolve_bridge_command(action: &str) -> Result<Command, String> {
    let current_exe = std::env::current_exe().map_err(|e| e.to_string())?;
    let exe_dir = current_exe
        .parent()
        .ok_or_else(|| "Failed to resolve executable directory".to_string())?;

    let sidecar_name = if cfg!(target_os = "windows") {
        "flac-bridge.exe"
    } else {
        "flac-bridge"
    };

    // 1. Check installed sidecar next to the Tauri executable
    let installed_sidecar = exe_dir.join(sidecar_name);
    if installed_sidecar.exists() {
        let mut cmd = Command::new(&installed_sidecar);
        cmd.arg(action).arg("-");
        // Ensure sibling ffmpeg.exe and fpcalc.exe are discoverable
        if let Ok(path_env) = std::env::var("PATH") {
            let sep = if cfg!(target_os = "windows") { ";" } else { ":" };
            cmd.env("PATH", format!("{}{}{}", exe_dir.display(), sep, path_env));
        }
        #[cfg(target_os = "windows")]
        cmd.creation_flags(CREATE_NO_WINDOW);
        return Ok(cmd);
    }

    // 2. Fallback for local `npm run tauri dev`: use repository Python venv
    let root = find_workspace_root();
    let python = find_python_executable(&root);

    let mut cmd = Command::new(python);
    cmd.current_dir(&root);
    cmd.env("PYTHONPATH", root.join("src"));
    cmd.env("PYTHONIOENCODING", "utf-8");
    cmd.env("PYTHONUTF8", "1");
    cmd.arg("-m")
        .arg("flac_injector.bridge")
        .arg(action)
        .arg("-");

    #[cfg(target_os = "windows")]
    cmd.creation_flags(CREATE_NO_WINDOW);

    Ok(cmd)
}

/// Execute a bridge command asynchronously and optionally stream progress events
async fn execute_bridge_command(
    app: Option<&AppHandle>,
    action: &str,
    params: Value,
) -> Result<Value, String> {
    let params_str = serde_json::to_string(&params).map_err(|e| e.to_string())?;

    let mut cmd = resolve_bridge_command(action)?;

    cmd.stdin(Stdio::piped());
    cmd.stdout(Stdio::piped());
    cmd.stderr(Stdio::piped());

    let mut child = cmd.spawn().map_err(|e| format!("Failed to spawn Python bridge: {e}"))?;

    // Pipe JSON params via stdin to completely avoid Windows cmdline length limits (os error 206)
    if let Some(mut stdin) = child.stdin.take() {
        use tokio::io::AsyncWriteExt;
        let _ = stdin.write_all(params_str.as_bytes()).await;
        let _ = stdin.flush().await;
        drop(stdin);
    }

    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| "Failed to capture stdout of Python bridge".to_string())?;

    // Capture stderr concurrently to preserve Python tracebacks on error
    let stderr_task = if let Some(stderr) = child.stderr.take() {
        Some(tokio::spawn(async move {
            let mut err_lines = BufReader::new(stderr).lines();
            let mut captured = Vec::new();
            while let Ok(Some(line)) = err_lines.next_line().await {
                captured.push(line);
            }
            captured.join("\n")
        }))
    } else {
        None
    };

    let mut reader = BufReader::new(stdout).lines();
    let mut final_result: Option<Value> = None;
    let mut error_messages: Vec<String> = Vec::new();

    while let Ok(Some(line)) = reader.next_line().await {
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }

        if let Ok(event) = serde_json::from_str::<Value>(trimmed) {
            let event_type = event.get("type").and_then(|t| t.as_str()).unwrap_or("");
            if event_type == "progress" {
                if let Some(app_handle) = app {
                    let _ = app_handle.emit("injector-progress", &event);
                }
            } else if event_type == "result" {
                if let Some(data) = event.get("data") {
                    final_result = Some(data.clone());
                }
            } else if event_type == "error" {
                if let Some(msg) = event.get("message").and_then(|m| m.as_str()) {
                    error_messages.push(msg.to_string());
                }
            }
        }
    }

    let status = child
        .wait()
        .await
        .map_err(|e| format!("Bridge process failed: {e}"))?;

    let stderr_output = if let Some(handle) = stderr_task {
        handle.await.unwrap_or_default()
    } else {
        String::new()
    };

    if !status.success() && final_result.is_none() {
        let err_desc = if !error_messages.is_empty() {
            error_messages.join("\n")
        } else if !stderr_output.trim().is_empty() {
            stderr_output
        } else {
            format!("Process exited with status code: {:?}", status.code())
        };
        return Err(format!("Bridge error during '{action}': {err_desc}"));
    }

    final_result.ok_or_else(|| {
        if !error_messages.is_empty() {
            error_messages.join("\n")
        } else if !stderr_output.trim().is_empty() {
            stderr_output
        } else {
            "No result returned by Python bridge".to_string()
        }
    })
}

#[tauri::command]
async fn check_system_health(app: AppHandle) -> Result<Value, String> {
    execute_bridge_command(Some(&app), "health", json!({})).await
}

#[tauri::command]
async fn run_scan(
    app: AppHandle,
    paths: Vec<String>,
    recursive: bool,
    only_incomplete: bool,
) -> Result<Value, String> {
    let params = json!({
        "paths": paths,
        "recursive": recursive,
        "only_incomplete": only_incomplete,
    });
    execute_bridge_command(Some(&app), "scan", params).await
}

#[tauri::command]
async fn run_inspect(
    app: AppHandle,
    path: String,
    include_art_base64: Option<bool>,
) -> Result<Value, String> {
    let params = json!({
        "path": path,
        "include_art_base64": include_art_base64.unwrap_or(true),
    });
    execute_bridge_command(Some(&app), "inspect", params).await
}

#[tauri::command]
async fn run_fingerprint(app: AppHandle, path: String) -> Result<Value, String> {
    let params = json!({ "path": path });
    execute_bridge_command(Some(&app), "fingerprint", params).await
}

#[tauri::command]
async fn run_inject(
    app: AppHandle,
    paths: Vec<String>,
    dry_run: bool,
    threshold: f64,
    overwrite: bool,
    convert_wav: bool,
    recursive: bool,
) -> Result<Value, String> {
    let params = json!({
        "paths": paths,
        "dry_run": dry_run,
        "threshold": threshold,
        "overwrite": overwrite,
        "convert_wav": convert_wav,
        "recursive": recursive,
    });
    execute_bridge_command(Some(&app), "inject", params).await
}

#[tauri::command]
async fn run_convert(
    app: AppHandle,
    paths: Vec<String>,
    output_dir: Option<String>,
    inject: bool,
    delete_original: bool,
    compression_level: u32,
    threshold: f64,
    dry_run: bool,
) -> Result<Value, String> {
    let params = json!({
        "paths": paths,
        "output_dir": output_dir,
        "inject_tags": inject,
        "delete_original": delete_original,
        "compression_level": compression_level,
        "threshold": threshold,
        "dry_run": dry_run,
    });
    execute_bridge_command(Some(&app), "convert", params).await
}

#[tauri::command]
async fn get_settings(app: AppHandle) -> Result<Value, String> {
    execute_bridge_command(Some(&app), "get_env", json!({})).await
}

#[tauri::command]
async fn save_settings(app: AppHandle, settings: Value) -> Result<Value, String> {
    let params = json!({ "settings": settings });
    execute_bridge_command(Some(&app), "set_env", params).await
}

#[tauri::command]
fn minimize_window(window: Window) -> Result<(), String> {
    window.minimize().map_err(|e| e.to_string())
}

#[tauri::command]
fn maximize_window(window: Window) -> Result<(), String> {
    if window.is_maximized().map_err(|e| e.to_string())? {
        window.unmaximize().map_err(|e| e.to_string())
    } else {
        window.maximize().map_err(|e| e.to_string())
    }
}

#[tauri::command]
async fn pick_audio_files(app: AppHandle) -> Result<Vec<String>, String> {
    let (tx, rx) = tokio::sync::oneshot::channel();
    app.dialog()
        .file()
        .add_filter("Audio Files", &["flac", "mp3", "wav", "wave", "aiff", "aif"])
        .pick_files(move |paths| {
            let _ = tx.send(paths);
        });
    let selected = rx.await.map_err(|e| e.to_string())?;
    match selected {
        Some(file_paths) => Ok(file_paths.into_iter().map(|p| p.to_string()).collect()),
        None => Ok(Vec::new()),
    }
}

#[tauri::command]
async fn pick_library_folder(app: AppHandle) -> Result<Option<String>, String> {
    let (tx, rx) = tokio::sync::oneshot::channel();
    app.dialog()
        .file()
        .pick_folder(move |dir| {
            let _ = tx.send(dir);
        });
    let selected = rx.await.map_err(|e| e.to_string())?;
    Ok(selected.map(|p| p.to_string()))
}

#[tauri::command]
fn close_window(window: Window) -> Result<(), String> {
    window.close().map_err(|e| e.to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let window = app.get_webview_window("main").unwrap();

            #[cfg(target_os = "windows")]
            {
                // Apply dark obsidian-tinted Windows 11 Acrylic blur; fall back to Mica if unsupported
                if apply_acrylic(&window, Some((10, 12, 22, 170))).is_err() {
                    let _ = apply_mica(&window, Some(true));
                }
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            check_system_health,
            run_scan,
            run_inspect,
            run_fingerprint,
            run_inject,
            run_convert,
            get_settings,
            save_settings,
            minimize_window,
            maximize_window,
            close_window,
            pick_audio_files,
            pick_library_folder,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
