"""Windows headless subprocess patching to eliminate console window popups (conhost.exe)."""

from __future__ import annotations

import subprocess
import sys
from typing import Any


def install_windows_headless_subprocess_patch() -> None:
    """
    Globally patch subprocess.Popen on Windows so that ALL child binaries
    (including fpcalc.exe spawned inside third-party pyacoustid and ffmpeg.exe)
    always run with CREATE_NO_WINDOW (0x08000000) and SW_HIDE.
    """
    if sys.platform != "win32":
        return

    CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    STARTF_USESHOWWINDOW = getattr(subprocess, "STARTF_USESHOWWINDOW", 0x00000001)
    SW_HIDE = getattr(subprocess, "SW_HIDE", 0)

    _OriginalPopen = subprocess.Popen
    if getattr(_OriginalPopen, "_is_silent_windows_popen", False):
        return

    class SilentWindowsPopen(_OriginalPopen):
        _is_silent_windows_popen = True

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs["creationflags"] = kwargs.get("creationflags", 0) | CREATE_NO_WINDOW
            startupinfo = kwargs.get("startupinfo")
            if startupinfo is None:
                startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = SW_HIDE
            kwargs["startupinfo"] = startupinfo
            super().__init__(*args, **kwargs)

    subprocess.Popen = SilentWindowsPopen  # type: ignore[misc]


def get_windows_headless_kwargs() -> dict[str, Any]:
    """Return creationflags & startupinfo for headless subprocess execution on Windows."""
    if sys.platform != "win32":
        return {}
    si = subprocess.STARTUPINFO()
    si.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0x00000001)
    si.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
    return {
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
        "startupinfo": si,
    }


# Execute immediately on import
install_windows_headless_subprocess_patch()
