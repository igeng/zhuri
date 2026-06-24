#!/usr/bin/env python3
"""Enforce per-package coverage floors from coverage.xml (SPEC §0.1 / A14).

Overall ≥85% is enforced by pytest --cov-fail-under=85. This script adds the
stricter ≥90% floors for the safety-critical packages: state/, orchestrator/,
watchdog/, and config.py.
"""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Paths are relative to the coverage <source> root (the zhuri/ package dir),
# so prefixes are package-relative (e.g. "state", not "zhuri/state").
FLOORS = {
    "state": 90.0,
    "orchestrator": 90.0,
    "watchdog": 90.0,
    "config.py": 90.0,
}


def _norm(filename: str) -> str:
    return filename.replace("\\", "/")


def main() -> int:
    xml_path = Path("coverage.xml")
    if not xml_path.exists():
        print("coverage.xml not found; run pytest --cov-report=xml first", file=sys.stderr)
        return 2

    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Aggregate line hits/total per floor prefix.
    hits: dict[str, int] = {k: 0 for k in FLOORS}
    total: dict[str, int] = {k: 0 for k in FLOORS}

    for cls in root.iter("class"):
        filename = _norm(cls.get("filename", ""))
        for prefix in FLOORS:
            if filename == prefix or filename.startswith(prefix + "/"):
                for line in cls.iter("line"):
                    total[prefix] += 1
                    if int(line.get("hits", "0")) > 0:
                        hits[prefix] += 1

    failed = False
    for prefix, floor in sorted(FLOORS.items()):
        if total[prefix] == 0:
            print(f"FAIL {prefix}: no coverage data found")
            failed = True
            continue
        pct = 100.0 * hits[prefix] / total[prefix]
        status = "ok  " if pct >= floor else "FAIL"
        print(f"{status} {prefix}: {pct:.1f}% (floor {floor:.0f}%)")
        if pct < floor:
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
