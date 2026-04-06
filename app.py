"""Vercel entrypoint — re-exports the FastAPI app."""

import os

# Suppress gitpython error when git binary is not available (Vercel serverless)
os.environ.setdefault("GIT_PYTHON_REFRESH", "quiet")

from fastapi import FastAPI
from fastapi.responses import JSONResponse

# This variable MUST exist at module level for Vercel's static analysis.
app = FastAPI()

# Try loading the real app; if it fails, serve diagnostics.
try:
    from backend.main import app  # noqa: F811
except Exception as _exc:
    import traceback as _tb

    _error_detail = _tb.format_exc()
    _error_msg = str(_exc)

    @app.get("/api/health")
    @app.get("/api/debug")
    @app.get("/{path:path}")
    async def _diagnostic(path: str = ""):
        return JSONResponse(
            {
                "status": "import_error",
                "error": _error_msg,
                "traceback": _error_detail,
            },
            status_code=500,
        )
