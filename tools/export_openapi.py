#!/usr/bin/env python3
import json
import os
from pathlib import Path


def main():
    # Ensure we import the app correctly whether run from project root or elsewhere
    import sys
    here = Path(__file__).resolve().parent.parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))

    from api.main import app  # noqa: WPS433

    # Allow overriding base URL via env
    os.environ.setdefault("API_BASE_URL", os.getenv("API_BASE_URL", "http://127.0.0.1:8000"))

    schema = app.openapi()

    docs_dir = here / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    out_path = docs_dir / "openapi.json"
    out_path.write_text(json.dumps(schema, indent=2))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()

