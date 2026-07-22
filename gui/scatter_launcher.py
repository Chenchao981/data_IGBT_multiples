#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Launch the packaged FT scatter frontend from the desktop GUI."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import webbrowser
from pathlib import Path
from urllib.parse import quote


DEFAULT_PORT = 8502


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
    raise FileNotFoundError("未找到 FT 散点图前端文件 frontend/ft_scatter_app.py")


def _port_is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def launch_ft_scatter(manifest_path: Path | str, port: int = DEFAULT_PORT) -> str:
    """Start Streamlit if needed, open the manifest URL, and return that URL."""
    manifest_path = Path(manifest_path).resolve()
    if not manifest_path.is_file():
        raise FileNotFoundError(f"散点图数据清单不存在: {manifest_path}")
    app_path = find_scatter_app()
    url = f"http://127.0.0.1:{port}/?manifest={quote(str(manifest_path))}"

    if not _port_is_open(port):
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
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(app_path),
                "--server.headless=true",
                f"--server.port={port}",
                "--browser.gatherUsageStats=false",
            ],
            cwd=str(app_path.parent.parent),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )

    webbrowser.open(url)
    return url
