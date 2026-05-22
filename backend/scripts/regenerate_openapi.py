"""Dump the FastAPI app's OpenAPI schema to ``backend/openapi.json``.

Run from ``backend/`` after touching any router/schema:

    uv run python scripts/regenerate_openapi.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app  # noqa: E402

OUTPUT_PATH = BACKEND_ROOT / "openapi.json"


def main() -> None:
    spec = app.openapi()
    OUTPUT_PATH.write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
