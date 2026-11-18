"""WebSocket JSON-RPC server for flac-meta-injector.

Allows pure web clients (browsers outside Tauri) to execute audio scanning,
metadata inspection, fingerprinting, waterfall injection, and WAV-to-FLAC conversion
with real-time progress streaming over WebSockets.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import string
import sys
from pathlib import Path
from typing import Any

import websockets

from flac_injector import bridge

logger = logging.getLogger("flac_injector.server")

# Active WebSocket connections
CONNECTED_CLIENTS: set[Any] = set()
MAIN_LOOP: asyncio.AbstractEventLoop | None = None


def _handle_bridge_event(event: dict[str, Any]) -> None:
    """Callback hooked into bridge.emit_event to broadcast progress to all clients."""
    if not CONNECTED_CLIENTS:
        return
    msg = json.dumps({
        "type": "event",
        "event": "injector-progress",
        "payload": event,
    })
    if MAIN_LOOP and MAIN_LOOP.is_running():
        for ws in list(CONNECTED_CLIENTS):
            MAIN_LOOP.create_task(_safe_send(ws, msg))


async def _safe_send(ws: Any, message: str) -> None:
    """Send message to a WebSocket client ignoring disconnect errors."""
    try:
        await ws.send(message)
    except Exception:
        pass


def _list_filesystem(target_path: str | None = None) -> dict[str, Any]:
    """List directory contents or system drives for web path browsing."""
    supported_exts = {".flac", ".mp3", ".wav", ".wave", ".aiff", ".aif"}

    if not target_path or target_path.strip() == "":
        # If on Windows and no path provided, list drives
        if sys.platform.startswith("win"):
            drives = []
            for letter in string.ascii_uppercase:
                drive = f"{letter}:\\"
                if os.path.exists(drive):
                    drives.append(drive)
            return {
                "current": "",
                "parent": None,
                "directories": drives,
                "files": [],
            }
        target_path = str(Path.home())

    curr = Path(target_path).resolve()
    if not curr.exists() or not curr.is_dir():
        curr = Path.home()

    directories: list[str] = []
    files: list[str] = []

    try:
        for entry in sorted(curr.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
            if entry.is_dir():
                directories.append(str(entry))
            elif entry.is_file() and entry.suffix.lower() in supported_exts:
                files.append(str(entry))
    except (PermissionError, OSError):
        pass

    parent = str(curr.parent) if curr.parent != curr else None

    return {
        "current": str(curr),
        "parent": parent,
        "directories": directories,
        "files": files,
    }


async def handle_rpc_action(action: str, params: dict[str, Any]) -> Any:
    """Dispatch JSON-RPC action to corresponding bridge function."""
    if action == "check_system_health":
        return bridge.run_health_check()

    if action == "run_scan":
        paths = params.get("paths", [])
        recursive = params.get("recursive", True)
        only_incomplete = params.get("onlyIncomplete", False)
        return bridge.run_scan_command(paths, recursive=recursive, only_incomplete=only_incomplete)

    if action == "run_inspect":
        path_str = params["path"]
        include_art_base64 = params.get("includeArtBase64", True)
        return bridge.run_inspect_command(path_str, include_art_base64=include_art_base64)

    if action == "run_fingerprint":
        path_str = params["path"]
        return bridge.run_fingerprint_command(path_str)

    if action == "run_inject":
        return await bridge.run_inject_command(
            paths=params.get("paths", []),
            threshold=float(params.get("threshold", 0.70)),
            dry_run=bool(params.get("dryRun", False)),
            overwrite=bool(params.get("overwrite", False)),
            convert_wav=bool(params.get("convertWav", True)),
            recursive=bool(params.get("recursive", True)),
            song_link=params.get("songLink"),
        )

    if action == "run_convert":
        return await bridge.run_convert_command(
            paths=params.get("paths", []),
            output_dir=params.get("outputDir"),
            inject=bool(params.get("inject", True)),
            delete_original=bool(params.get("deleteOriginal", False)),
            compression_level=int(params.get("compressionLevel", 8)),
            threshold=float(params.get("threshold", 0.70)),
            dry_run=bool(params.get("dryRun", False)),
        )

    if action in ("get_settings", "get_env"):
        return bridge.get_env_settings()

    if action in ("save_settings", "set_env"):
        settings = params.get("settings", {})
        return bridge.save_env_settings(settings)

    if action == "browse_filesystem":
        return _list_filesystem(params.get("path"))

    raise ValueError(f"Unknown RPC action: {action}")


async def connection_handler(websocket: Any) -> None:
    """Handle individual WebSocket client connection and message loop."""
    CONNECTED_CLIENTS.add(websocket)
    try:
        async for raw_message in websocket:
            try:
                msg = json.loads(raw_message)
            except Exception as parse_err:
                await websocket.send(json.dumps({"error": f"Invalid JSON: {parse_err}"}))
                continue

            req_id = msg.get("id")
            action = msg.get("action")
            params = msg.get("params", {})

            if not action:
                await websocket.send(json.dumps({
                    "id": req_id,
                    "result": None,
                    "error": "Missing 'action' field in request",
                }))
                continue

            try:
                result = await handle_rpc_action(action, params)
                response = {
                    "id": req_id,
                    "result": result,
                    "error": None,
                }
            except Exception as exc:
                logger.exception("Error executing action %s", action)
                response = {
                    "id": req_id,
                    "result": None,
                    "error": str(exc),
                }

            await websocket.send(json.dumps(response, ensure_ascii=False))
    finally:
        CONNECTED_CLIENTS.discard(websocket)


async def start_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Start the WebSocket RPC server."""
    global MAIN_LOOP
    MAIN_LOOP = asyncio.get_running_loop()
    bridge.set_event_hook(_handle_bridge_event)

    logger.info("Starting flac-meta-injector WebSocket server on ws://%s:%d", host, port)
    async with websockets.serve(connection_handler, host, port):
        await asyncio.Future()  # run forever


def main() -> None:
    """CLI entrypoint for running the WebSocket server directly."""
    import argparse

    parser = argparse.ArgumentParser(description="flac-meta-injector WebSocket backend server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Bind port (default: 8765)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    try:
        asyncio.run(start_server(host=args.host, port=args.port))
    except KeyboardInterrupt:
        logger.info("Server stopped by user")


if __name__ == "__main__":
    main()
