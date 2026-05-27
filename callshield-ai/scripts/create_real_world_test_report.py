"""create_real_world_test_report: copy the real-world test template with a timestamp."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "docs" / "real_world_test_report_template.md"


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a CallShield real-world test report from the template.")
    parser.add_argument("--out-dir", default="reports/real_world", help="Directory for the generated report.")
    parser.add_argument("--name", default="", help="Optional report name without extension.")
    args = parser.parse_args()

    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = args.name.strip() or f"real_world_test_{stamp}"
    out_path = out_dir / f"{name}.md"
    out_path.write_text(TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Created real-world test report: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
