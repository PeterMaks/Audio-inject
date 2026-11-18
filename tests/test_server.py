"""Unit tests for the flac_injector WebSocket server module."""

import asyncio
import json
from pathlib import Path

import pytest
import websockets

from flac_injector.server import (
    _handle_bridge_event,
    handle_rpc_action,
    start_server,
)


@pytest.mark.asyncio
async def test_handle_rpc_action_health():
    """Verify handle_rpc_action routes health check correctly."""
    res = await handle_rpc_action("check_system_health", {})
    assert "python_version" in res
    assert "ffmpeg" in res
    assert "env_status" in res


@pytest.mark.asyncio
async def test_handle_rpc_action_scan(tagged_flac: Path):
    """Verify handle_rpc_action routes scan command correctly."""
    res = await handle_rpc_action("run_scan", {"paths": [str(tagged_flac)]})
    assert res["total"] == 1
    assert res["items"][0]["filename"] == tagged_flac.name


@pytest.mark.asyncio
async def test_handle_rpc_action_inspect(tagged_flac: Path):
    """Verify handle_rpc_action routes inspect command correctly."""
    res = await handle_rpc_action(
        "run_inspect",
        {"path": str(tagged_flac), "includeArtBase64": True},
    )
    assert res["filename"] == tagged_flac.name
    assert res["has_cover_art"] is True


@pytest.mark.asyncio
async def test_handle_rpc_action_browse_filesystem(tmp_path: Path):
    """Verify filesystem directory listing for web client browsing."""
    sub_dir = tmp_path / "subdir"
    sub_dir.mkdir()
    sample_file = tmp_path / "test.flac"
    sample_file.write_bytes(b"dummy")

    res = await handle_rpc_action("browse_filesystem", {"path": str(tmp_path)})
    assert str(sub_dir) in res["directories"]
    assert str(sample_file) in res["files"]


@pytest.mark.asyncio
async def test_handle_rpc_unknown_action():
    """Verify unknown action raises ValueError."""
    with pytest.raises(ValueError, match="Unknown RPC action"):
        await handle_rpc_action("non_existent_action", {})


@pytest.mark.asyncio
async def test_websocket_server_roundtrip(tagged_flac: Path):
    """Verify live WebSocket connection, request/response cycle, and event broadcasting."""
    port = 8769
    host = "127.0.0.1"

    # Start server in background task
    server_task = asyncio.create_task(start_server(host=host, port=port))
    await asyncio.sleep(0.15)  # Allow server to bind

    try:
        uri = f"ws://{host}:{port}"
        async with websockets.connect(uri) as ws:
            # 1. Test RPC request
            req = {
                "id": "req-1",
                "action": "run_scan",
                "params": {"paths": [str(tagged_flac)]},
            }
            await ws.send(json.dumps(req))

            raw_res = await asyncio.wait_for(ws.recv(), timeout=5.0)
            res = json.loads(raw_res)

            assert res["id"] == "req-1"
            assert res["error"] is None
            assert res["result"]["total"] == 1

            # 2. Test event broadcast
            test_event = {
                "stage": "acoustid",
                "file": "test.flac",
                "percent": 50.0,
                "message": "Resolving fingerprint...",
            }
            _handle_bridge_event(test_event)

            raw_event = await asyncio.wait_for(ws.recv(), timeout=5.0)
            evt = json.loads(raw_event)
            assert evt["type"] == "event"
            assert evt["event"] == "injector-progress"
            assert evt["payload"]["stage"] == "acoustid"
            assert evt["payload"]["percent"] == 50.0

    finally:
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass
