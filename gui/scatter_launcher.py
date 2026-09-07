#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Launch the packaged FT scatter/box frontend from the desktop GUI."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import webbrowser
from pathlib import Path
from threading import RLock
from urllib.parse import quote


DEFAULT_PORT = 8502
_LAUNCH_LOCK = RLock()
_MANAGED_PROCESS: subprocess.Popen | None = None
_MANAGED_PORT: int | None = None


def _app_candidates() -> list[Path]:
    candidates: list[Path] = []
    executable_path = Path(sys.argv[0]).resolve()
    if executable_path.suffix.lower() == ".pyz":
        candidates.append(executable_path.parent / "frontend" / "ft_scatter_app.py")
    candidates.append(Path(__file__).resolve().parent.parent / "frontend" / "ft_scatter_app.py")
    candidates.append(Path.cwd() / "frontend" / "ft_scatter_app.py")
    return candidates


def find_scatter_app() -> Path:
    for candidate in _app_candidates():
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("未找到 FT 图表前端文件 frontend/ft_scatter_app.py")


def _port_is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _managed_port() -> int | None:
    """Return the port of this GUI process's live Streamlit child only."""

    global _MANAGED_PROCESS, _MANAGED_PORT
    if _MANAGED_PROCESS is None or _MANAGED_PORT is None:
        return None
    try:
        alive = _MANAGED_PROCESS.poll() is None
    except (OSError, ValueError):
        alive = False
    if alive:
        return _MANAGED_PORT
    _MANAGED_PROCESS = None
    _MANAGED_PORT = None
    return None


def _next_available_port(preferred_port: int) -> int:
    """Choose the first free localhost port at or above ``preferred_port``."""

    if not isinstance(preferred_port, int) or not 1 <= preferred_port <= 65_535:
        raise ValueError(f"无效的 FT 图表服务端口: {preferred_port!r}")
    for candidate in range(preferred_port, 65_536):
        if not _port_is_open(candidate):
            return candidate
    raise OSError(f"从端口 {preferred_port} 起没有可用的 FT 图表服务端口")


def launch_ft_scatter(manifest_path: Path | str, port: int = DEFAULT_PORT) -> str:
    """Start Streamlit if needed, open the manifest URL, and return that URL."""
    global _MANAGED_PROCESS, _MANAGED_PORT

    manifest_path = Path(manifest_path).resolve()
    if not manifest_path.is_file():
        raise FileNotFoundError(f"FT 图表数据清单不存在: {manifest_path}")

    with _LAUNCH_LOCK:
        active_port = _managed_port()
        if active_port is None:
            active_port = _next_available_port(port)
            app_path = find_scatter_app()
            env = os.environ.copy()
            env["FT_SCATTER_MANIFEST"] = str(manifest_path)
            python_paths = [str(app_path.parent.parent)]
            executable_path = Path(sys.argv[0]).resolve()
            if executable_path.suffix.lower() == ".pyz":
                python_paths.insert(0, str(executable_path))
            existing = env.get("PYTHONPATH")
            if existing:
                python_paths.append(existing)
            env["PYTHONPATH"] = os.pathsep.join(python_paths)

            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            _MANAGED_PROCESS = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "streamlit",
                    "run",
                    str(app_path),
                    "--server.headless=true",
                    f"--server.port={active_port}",
                    "--browser.gatherUsageStats=false",
                ],
                cwd=str(app_path.parent.parent),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
            _MANAGED_PORT = active_port

        url = (
            f"http://127.0.0.1:{active_port}/"
            f"?manifest={quote(str(manifest_path))}"
        )

    webbrowser.open(url)
    return url
