#!/usr/bin/env python3
"""Download a marketplace asset and print its checksum and size.

Usage:
  python3 scripts/asset_meta.py <url> [--expected-sha256 HEX] [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import (  # noqa: E402
    DownloadError,
    classify_url,
    download,
    human_size,
    is_network_error,
    print_network_hint,
)


def build_meta(url: str, timeout: int = 300) -> dict:
    kind, immutable, policy_ok, warnings = classify_url(url)
    fd, tmp_name = tempfile.mkstemp(prefix="xime-asset-")
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        sha256, size_bytes = download(url, tmp_path, timeout=timeout)
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass
    return {
        "url": url,
        "sha256": sha256,
        "size": human_size(size_bytes),
        "sizeBytes": size_bytes,
        "immutable": immutable,
        "policy_ok": policy_ok,
        "kind": kind,
        "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--expected-sha256")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit 3 when the URL is not a GitHub Release asset",
    )
    args = parser.parse_args(argv)

    try:
        meta = build_meta(args.url, timeout=args.timeout)
    except DownloadError as exc:
        print(f"error: 下载失败: {exc}", file=sys.stderr)
        if is_network_error(exc):
            print_network_hint(str(exc))
        return 2

    if args.expected_sha256:
        expected = args.expected_sha256.strip().lower()
        if expected != meta["sha256"]:
            print(
                "error: sha256 不一致\n"
                f"  期望: {expected}\n"
                f"  实际: {meta['sha256']}",
                file=sys.stderr,
            )
            return 4

    if args.json:
        print(json.dumps(meta, ensure_ascii=False, indent=2))
    else:
        print(f"url:       {meta['url']}")
        print(f"sha256:    {meta['sha256']}")
        print(f"size:      {meta['size']} ({meta['sizeBytes']} bytes)")
        print(f"kind:      {meta['kind']}")
        print(f"immutable: {'yes' if meta['immutable'] else 'no'}")
        print(f"policy:    {'ok' if meta['policy_ok'] else 'warning'}")
        for warning in meta["warnings"]:
            print(f"warning:   {warning}")

    if args.strict and not meta["policy_ok"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
