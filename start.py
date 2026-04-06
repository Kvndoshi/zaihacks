"""
Friction — Single-command launcher.

    python start.py

Builds the frontend (if needed), then starts the server.
Both the API and the dashboard are served from the same port.
"""

import os
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT / "frontend"
DIST_DIR = FRONTEND_DIR / "dist"
BACKEND_DIR = ROOT / "backend"
ENV_FILE = BACKEND_DIR / ".env"
ENV_TEMPLATE = BACKEND_DIR / ".env.template"


def ensure_env():
    """Create .env from template if it doesn't exist."""
    if not ENV_FILE.exists() and ENV_TEMPLATE.exists():
        ENV_FILE.write_text(ENV_TEMPLATE.read_text())
        print("[friction] Created backend/.env from template -- add your GEMINI_API_KEY.")


def install_frontend():
    """Run npm install if node_modules is missing."""
    if not (FRONTEND_DIR / "node_modules").is_dir():
        print("[friction] Installing frontend dependencies...")
        subprocess.run(
            ["npm", "install"],
            cwd=str(FRONTEND_DIR),
            check=True,
            shell=True,
        )


def build_frontend():
    """Build frontend into dist/ if not already built (or if src is newer)."""
    needs_build = not DIST_DIR.is_dir()

    if not needs_build:
        dist_index = DIST_DIR / "index.html"
        if dist_index.exists():
            dist_mtime = dist_index.stat().st_mtime
            src_dir = FRONTEND_DIR / "src"
            for f in src_dir.rglob("*"):
                if f.is_file() and f.stat().st_mtime > dist_mtime:
                    needs_build = True
                    break
        else:
            needs_build = True

    if needs_build:
        print("[friction] Building frontend...")
        install_frontend()
        subprocess.run(
            ["npm", "run", "build"],
            cwd=str(FRONTEND_DIR),
            check=True,
            shell=True,
        )
        print("[friction] Frontend built successfully.")
    else:
        print("[friction] Frontend dist/ is up to date.")


def find_free_port(preferred: int) -> int:
    """Return preferred port if free, otherwise find the next available one."""
    for port in [preferred] + list(range(preferred + 1, preferred + 20)):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("0.0.0.0", port))
                return port
        except OSError:
            continue
    # Last resort: let OS pick
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("0.0.0.0", 0))
        return s.getsockname()[1]


def start_server():
    """Start the FastAPI server with uvicorn."""
    # Load .env
    from dotenv import load_dotenv
    load_dotenv(str(ENV_FILE))

    preferred = int(os.environ.get("PORT", "3000"))
    port = find_free_port(preferred)

    if port != preferred:
        print(f"[friction] Port {preferred} is busy, using {port} instead.")

    print(f"[friction] Starting Friction server on http://localhost:{port}")
    print(f"[friction] Dashboard:  http://localhost:{port}")
    print(f"[friction] API:        http://localhost:{port}/api/health")
    print()

    # Import app AFTER building frontend so _FRONTEND_DIST.is_dir() is True
    from backend.main import app

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    os.chdir(str(ROOT))
    ensure_env()
    build_frontend()
    start_server()
