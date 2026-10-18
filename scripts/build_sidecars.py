# scripts/build_sidecars.py
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
BINARIES_DIR = ROOT_DIR / "desktop" / "src-tauri" / "binaries"
BRIDGE_ENTRY = ROOT_DIR / "src" / "flac_injector" / "bridge.py"


def get_rust_target_triple() -> str:
    """Query rustc for the exact host target triple (e.g. x86_64-pc-windows-msvc)."""
    rustc_bin = shutil.which("rustc")
    if not rustc_bin:
        cargo_rustc = (
            Path.home()
            / ".cargo"
            / "bin"
            / ("rustc.exe" if platform.system() == "Windows" else "rustc")
        )
        if cargo_rustc.exists():
            rustc_bin = str(cargo_rustc)
        else:
            rustc_bin = "rustc"

    output = subprocess.check_output([rustc_bin, "-vV"], text=True)
    for line in output.splitlines():
        if line.startswith("host:"):
            return line.split(":", 1)[1].strip()
    raise RuntimeError("Unable to determine Rust host target triple from rustc -vV")


def build_python_bridge(target_triple: str, ext: str) -> Path:
    """Freeze flac_injector.bridge into a single-file executable via PyInstaller."""
    exe_name = f"flac-bridge-{target_triple}"
    print(f"[1/3] Building standalone Python bridge: {exe_name}{ext} ...")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--noconsole",
        "--name",
        exe_name,
        "--distpath",
        str(BINARIES_DIR),
        "--workpath",
        str(ROOT_DIR / "build" / "pyinstaller_work"),
        "--specpath",
        str(ROOT_DIR / "build"),
        "--paths",
        str(ROOT_DIR / "src"),
        "--collect-submodules",
        "flac_injector",
        "--collect-submodules",
        "mutagen",
        "--hidden-import",
        "pydantic_settings",
        "--hidden-import",
        "rapidfuzz",
        "--hidden-import",
        "PIL",
        "--hidden-import",
        "acoustid",
        str(BRIDGE_ENTRY),
    ]
    subprocess.run(cmd, check=True)
    built_path = BINARIES_DIR / f"{exe_name}{ext}"
    if not built_path.exists():
        raise FileNotFoundError(f"PyInstaller failed to produce {built_path}")
    return built_path


def stage_native_binary(binary_name: str, target_triple: str, ext: str) -> Path:
    """Locate ffmpeg or fpcalc on PATH (or winget/choco packages) and copy it with Tauri's target-triple suffix."""
    dest = BINARIES_DIR / f"{binary_name}-{target_triple}{ext}"
    source = shutil.which(binary_name)

    # Windows fallback search in WinGet or Chocolatey if not in current process PATH
    if not source and platform.system() == "Windows":
        local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
        candidates = list(
            (local_app_data / "Microsoft" / "WinGet" / "Packages").glob(
                f"**/{binary_name}.exe"
            )
        )
        if candidates:
            source = str(candidates[0])
        else:
            choco_bin = Path("C:/ProgramData/chocolatey/bin") / f"{binary_name}.exe"
            if choco_bin.exists():
                source = str(choco_bin)

    if not source:
        raise FileNotFoundError(
            f"Required binary '{binary_name}' was not found on PATH. "
            f"Install it first (e.g. choco install ffmpeg chromaprint or winget install)."
        )

    print(f"[*] Staging {source} -> {dest}")
    shutil.copy2(source, dest)
    os.chmod(dest, 0o755)
    return dest


def main() -> None:
    BINARIES_DIR.mkdir(parents=True, exist_ok=True)
    target_triple = get_rust_target_triple()
    ext = ".exe" if platform.system().lower() == "windows" else ""

    build_python_bridge(target_triple, ext)
    print("[2/3] Staging FFmpeg sidecar...")
    stage_native_binary("ffmpeg", target_triple, ext)
    print("[3/3] Staging Chromaprint (fpcalc) sidecar...")
    stage_native_binary("fpcalc", target_triple, ext)

    print("\nAll Tauri v2 sidecars successfully staged in:")
    for item in sorted(BINARIES_DIR.iterdir()):
        size_mb = item.stat().st_size / (1024 * 1024)
        print(f"  - {item.name} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
