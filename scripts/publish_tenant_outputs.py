#!/usr/bin/env python3
"""CLI: publish outputs to tenant release as one zip per output type."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from datetime import datetime, timezone

try:
    from scripts.output_assets import publish_outputs_per_type
except Exception:
    from output_assets import publish_outputs_per_type


def utc_date_yyyymmdd() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", required=True, help="Topic id (e.g., topic-01)")
    ap.add_argument("--date", default=None, help="UTC date YYYYMMDD (default: today)")
    default_root = "outputs"
    tid = os.getenv("TENANT_ID")
    use_tenant = os.getenv("USE_TENANT_OUTPUTS")
    if tid and (use_tenant is None or str(use_tenant).strip().lower() in ("1", "true", "yes", "y", "on")):
        default_root = f"tenants/{tid}/outputs"

    ap.add_argument("--outputs-root", default=default_root, help="Outputs root folder")
    args = ap.parse_args()

    date = args.date or utc_date_yyyymmdd()
    outputs_root = Path(args.outputs_root)

    tid = os.getenv("TENANT_ID", "0000000001")
    print(f"Publishing tenant outputs (tenant={tid}, topic={args.topic}, date={date})...")
    res = publish_outputs_per_type(outputs_root, args.topic, date)
    if not res:
        print("No matching outputs found to publish.")
    else:
        for k,v in sorted(res.items()):
            print(f"  ✓ Uploaded {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
