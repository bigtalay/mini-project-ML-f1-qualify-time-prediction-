"""Generate the OpenAPI contract for openapi-typescript."""
import json
import sys
from pathlib import Path

from .api import app

if __name__ == "__main__":
    Path(sys.argv[1]).write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False), encoding="utf-8")
