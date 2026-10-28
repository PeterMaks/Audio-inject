"""Verification tests for Windows headless subprocess patching."""

import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

import flac_injector
import flac_injector.bridge
import flac_injector.cli
import flac_injector.converter
import flac_injector.fingerprint
from flac_injector.subprocess_patch import (
    get_windows_headless_kwargs,
    install_windows_headless_subprocess_patch,
)


def test_is_silent_windows_popen_flag():
    """Verify that subprocess.Popen has _is_silent_windows_popen on Windows."""
    if sys.platform != "win32":
        pytest.skip("Windows-specific verification")

    assert getattr(subprocess.Popen, "_is_silent_windows_popen", False) is True


def test_get_windows_headless_kwargs():
    """Verify headless kwargs contain CREATE_NO_WINDOW and hidden startupinfo."""
    if sys.platform != "win32":
        kwargs = get_windows_headless_kwargs()
        assert kwargs == {}
        return

    kwargs = get_windows_headless_kwargs()
    assert "creationflags" in kwargs
    assert kwargs["creationflags"] & 0x08000000 == 0x08000000
    assert "startupinfo" in kwargs
    si = kwargs["startupinfo"]
    assert isinstance(si, subprocess.STARTUPINFO)
    assert si.dwFlags & subprocess.STARTF_USESHOWWINDOW
    assert si.wShowWindow == subprocess.SW_HIDE


def test_silent_popen_injects_flags():
    """Verify that creating a Popen process automatically applies headless flags."""
    if sys.platform != "win32":
        pytest.skip("Windows-specific verification")

    # Mock _OriginalPopen super().__init__ by inspecting kwargs passed to subprocess.Popen
    with patch.object(subprocess.Popen.__mro__[1], "__init__", return_value=None) as mock_super_init:
        subprocess.Popen(["dummy.exe"])
        mock_super_init.assert_called_once()
        args, kwargs = mock_super_init.call_args
        assert kwargs["creationflags"] & 0x08000000 == 0x08000000
        assert kwargs["startupinfo"].dwFlags & subprocess.STARTF_USESHOWWINDOW
        assert kwargs["startupinfo"].wShowWindow == subprocess.SW_HIDE
