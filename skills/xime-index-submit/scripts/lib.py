"""Shared helpers for the xime-index-submit skill.

Only standard-library modules are used here so the skill works without
installing anything beyond PyYAML for the YAML-facing commands.
"""

from __future__ import annotations

import hashlib
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

USER_AGENT = "Xime-Skill-Checksum/1.0"

_HEX_RE = re.compile(r"^[0-9a-f]{7,40}$", re.IGNORECASE)
_BRANCH_NAMES = {"main", "master", "develop", "dev", "trunk", "head"}


class DownloadError(RuntimeError):
    """Raised when an asset cannot be downloaded or read."""


def human_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    if n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    return f"{n / (1024 * 1024 * 1024):.2f} GB"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, dest: Path, timeout: int = 300) -> tuple[str, int]:
    """Download *url* to *dest*, returning (sha256, size_bytes)."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    digest = hashlib.sha256()
    total = 0
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            with open(dest, "wb") as handle:
                while True:
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    digest.update(chunk)
                    total += len(chunk)
                    handle.write(chunk)
    except Exception as exc:  # noqa: BLE001 - surface a single actionable error
        try:
            os.unlink(dest)
        except FileNotFoundError:
            pass
        raise DownloadError(str(exc)) from exc
    return digest.hexdigest(), total


def _ref_kind(ref: str) -> str:
    if _HEX_RE.match(ref):
        return "commit"
    if ref.lower() in _BRANCH_NAMES:
        return "branch"
    if re.match(r"^v?\d", ref):
        return "tag"
    if re.search(r"[-_]\d", ref):
        return "tag"
    return "branch"


def _warn(kind: str) -> list[str]:
    if kind == "github-release":
        return []
    return [
        "downloadUrl 必须是不可变的 GitHub Release 附件；"
        "raw/jsDelivr/分支地址会导致 sha256 失效。"
    ]


def classify_url(url: str) -> tuple[str, bool, bool, list[str]]:
    """Classify a download URL.

    Returns (kind, immutable, policy_ok, warnings). ``policy_ok`` is true only
    for GitHub Release assets, which is what xime-index requires for
    ``downloadUrl``. Screenshot URLs may use pinned raw/jsDelivr URLs; callers
    decide whether to enforce ``policy_ok`` for those.
    """
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path or ""
    query = urllib.parse.parse_qs(parsed.query or "")
    query_ref = (query.get("ref") or [""])[0]

    if host in {"github.com", "www.github.com"}:
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 5 and parts[2] == "releases" and parts[3] == "download":
            return "github-release", True, True, []
        if len(parts) >= 3 and parts[2] in {"blob", "raw"}:
            ref = query_ref or (parts[3] if len(parts) >= 4 else "")
            kind = "github-blob" if parts[2] == "blob" else "github-raw-web"
            return kind, _ref_kind(ref) in {"commit", "tag"}, False, _warn(kind)
        if len(parts) >= 5 and parts[2] == "archive":
            if parts[3] == "refs" and len(parts) >= 6:
                ref = parts[5]
                kind = (
                    "github-archive-tag"
                    if parts[4] == "tags"
                    else "github-archive-branch"
                )
            else:
                ref = parts[3]
                kind = "github-archive-" + _ref_kind(ref)
            return kind, _ref_kind(ref) in {"commit", "tag"}, False, _warn(kind)
        return "github-other", False, False, _warn("github-other")

    if host == "raw.githubusercontent.com":
        parts = [p for p in path.split("/") if p]
        ref = query_ref or (parts[2] if len(parts) >= 3 else "")
        kind = "github-raw-" + _ref_kind(ref)
        return kind, _ref_kind(ref) in {"commit", "tag"}, False, _warn(kind)

    if host == "cdn.jsdelivr.net":
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 4 and parts[0] == "gh" and "@" in parts[2]:
            ref = parts[2].rsplit("@", 1)[1]
            kind = "jsdelivr-" + _ref_kind(ref)
            return kind, _ref_kind(ref) in {"commit", "tag"}, False, _warn(kind)
        return "jsdelivr-other", False, False, _warn("jsdelivr-other")

    return "other", False, False, _warn("other")


def github_compare_url(upstream: str, fork_owner: str, branch: str) -> str:
    upstream = upstream.strip().rstrip("/")
    if upstream.startswith(("http://", "https://")):
        upstream = urllib.parse.urlparse(upstream).path.strip("/")
    if upstream.endswith(".git"):
        upstream = upstream[:-4]
    return (
        f"https://github.com/{upstream}/compare/main..."
        f"{fork_owner}:{branch}?expand=1"
    )
