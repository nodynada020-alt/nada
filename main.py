"""
Entry point for the AI Education Agent project.

This module runs the FastAPI backend which powers the modern frontend UI.
"""
from __future__ import annotations

import uvicorn


def main() -> None:
    """Run the FastAPI backend for the AI Education Agent."""
    uvicorn.run(
        "ui.oasis_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()

