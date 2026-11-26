#!/usr/bin/env python3
"""Update the topic selected in site.json using the repository's own code and data."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    topic = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))["topic"]
    return subprocess.call([sys.executable, "-B", str(ROOT / "build.py"), "--topic", topic, *sys.argv[1:]], cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
