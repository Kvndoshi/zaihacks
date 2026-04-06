"""Vercel entrypoint — re-exports the FastAPI app with diagnostic error reporting."""

import traceback

try:
    from backend.main import app  # noqa: F401
except Exception as exc:
    # If the real app fails to import, serve a diagnostic FastAPI
    # that reports the exact error so we can fix it.
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    app = FastAPI()

    _error_detail = traceback.format_exc()

    @app.get("/api/health")
    @app.get("/api/debug")
    @app.get("/{path:path}")
    async def diagnostic(path: str = ""):
        return JSONResponse(
            {
                "status": "import_error",
                "error": str(exc),
                "traceback": _error_detail,
            },
            status_code=500,
        )
