"""``python -m sunday_clays.api.export_openapi --out <path>``: needs no env vars and no DB."""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from sunday_clays.api.app import create_app


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the API's OpenAPI schema as JSON.")
    parser.add_argument("--out", type=Path, required=True, help="output file path")
    args = parser.parse_args(argv)
    out: Path = args.out
    schema = create_app().openapi()
    out.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
