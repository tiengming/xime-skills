#!/usr/bin/env python3
"""Preflight checks for a xime-index submission.

Usage:
  python3 scripts/preflight.py --repo /path/to/xime-index
      [--type layout|plugin-v2|plugin-v1|rime|model]
      [--check-rules] [--write-lock] [--lock PATH] [--json]

Exit codes: 0 pass, 2 required failure, 3 warnings only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import USER_AGENT, is_network_error, print_network_hint  # noqa: E402
from tools import (  # noqa: E402
    GhAuth,
    ToolInfo,
    check_gh_auth,
    gh_install_hint,
    resolve_tools,
)

UPSTREAM_REPO = "ximeiorg/xime-index"
UPSTREAM_BRANCH = "main"
RULE_FILES = [
    "CONTRIBUTING.md",
    "LAYOUT_SPEC.md",
    "scripts/ci-update.py",
    "scripts/lib.py",
]
RAW_BASE = (
    f"https://raw.githubusercontent.com/{UPSTREAM_REPO}/{UPSTREAM_BRANCH}"
)
COMMIT_API = f"https://api.github.com/repos/{UPSTREAM_REPO}/commits/{UPSTREAM_BRANCH}"
DEFAULT_LOCK_PATH = (
    Path(__file__).resolve().parent.parent / "references" / "upstream.lock.json"
)

TOOLS = ["python3", "git", "curl", "gh", "uv", "npx"]
REQUIRED_TOOLS = ["python3", "git", "curl"]
OPTIONAL_TOOL_HINTS = {
    "gh": "无 gh 时将输出浏览器 PR 链接",
    "uv": "无 uv 时用 python3 直接运行 ci-update.py",
    "npx": "无 npx 时手动复制技能目录安装",
}


def check_tool_details(**kwargs) -> dict[str, ToolInfo]:
    """Return path plus how each tool was found (PATH / fallback / missing)."""
    return resolve_tools(tuple(TOOLS), **kwargs)


def check_tools(**kwargs) -> dict[str, str | None]:
    """Return the resolved path (or None) for each expected tool."""
    return {
        name: info.path for name, info in check_tool_details(**kwargs).items()
    }


def _gh_auth_notes(auth: GhAuth) -> list[str]:
    """Human-readable next steps for the current gh login state."""
    if auth.state == "authenticated":
        notes: list[str] = []
        target = f"github.com 账号 {auth.account}" if auth.account else "github.com"
        via = "（使用环境变量 GH_TOKEN/GITHUB_TOKEN）" if auth.via_env_token else ""
        notes.append(f"已登录 {target}{via}")
        if auth.missing_scopes:
            blocking = [
                scope for scope in auth.missing_scopes if scope in {"repo"}
            ]
            if blocking:
                notes.append(
                    "token 缺少 "
                    + ", ".join(blocking)
                    + " scope，无法 push / 开 PR；运行 gh auth refresh -h github.com -s "
                    + blocking[0]
                )
            else:
                notes.append(
                    "gh 提示缺少 scope："
                    + ", ".join(auth.missing_scopes)
                    + "（与本流程无关，可忽略）"
                )
        return notes
    if auth.state == "not-authenticated":
        return ["已安装但未登录：运行 gh auth login（需要用户交互）"]
    if auth.state == "unavailable":
        return [f"无法读取登录状态：{auth.detail}"]
    return []


def _git_config_path(repo: Path) -> Path | None:
    dotgit = repo / ".git"
    if dotgit.is_dir():
        return dotgit / "config"
    if dotgit.is_file():
        try:
            content = dotgit.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        if content.startswith("gitdir:"):
            gitdir = Path(content.split(":", 1)[1].strip())
            if not gitdir.is_absolute():
                gitdir = repo / gitdir
            return gitdir / "config"
    return None


def check_repo(path: Path) -> tuple[list[str], list[str]]:
    """Check that *path* looks like a xime-index checkout."""
    errors: list[str] = []
    warnings: list[str] = []
    path = Path(path)
    if not path.is_dir():
        return [f"仓库路径不存在或不是目录: {path}"], []

    if not (path / "src").is_dir():
        errors.append(f"缺少 src/ 目录，可能不是 xime-index 仓库: {path}")
    if not (path / "scripts" / "ci-update.py").is_file():
        errors.append("缺少 scripts/ci-update.py，无法运行本地验证")
    for name in ("CONTRIBUTING.md", "LAYOUT_SPEC.md"):
        if not (path / name).is_file():
            warnings.append(f"缺少 {name}（上游结构可能已变化）")

    config = _git_config_path(path)
    if config is None or not config.is_file():
        warnings.append("未找到 .git/config，无法确认 upstream remote")
    else:
        try:
            text = config.read_text(encoding="utf-8")
        except OSError as exc:
            warnings.append(f"无法读取 .git/config: {exc}")
        else:
            if not re.search(r'\[remote\s+"upstream"\]', text):
                warnings.append(
                    "未配置 upstream remote（建议指向 ximeiorg/xime-index）"
                )
    return errors, warnings


def _fetch(url: str, timeout: int = 20) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def check_rules(
    repo: Path,
    write_lock: bool = False,
    lock_path: Path | None = None,
    timeout: int = 20,
) -> tuple[list[str], list[str]]:
    """Fetch upstream rule files and compare them with the local snapshot."""
    errors: list[str] = []
    warnings: list[str] = []
    lock_path = Path(lock_path) if lock_path is not None else DEFAULT_LOCK_PATH

    fetched: dict[str, bytes] = {}
    blocked: str | None = None
    for rel in RULE_FILES:
        try:
            fetched[rel] = _fetch(f"{RAW_BASE}/{rel}", timeout=timeout)
        except Exception as exc:  # noqa: BLE001 - report, do not crash
            warnings.append(f"无法获取上游规则 {rel}: {exc}")
            if blocked is None and is_network_error(exc):
                blocked = str(exc)

    if blocked is not None:
        warnings.append(
            "网络请求失败，疑似网络受阻；如需代理请先设置 "
            "http_proxy/https_proxy 再重试（详见下方提示）"
        )
        print_network_hint(blocked)

    if write_lock:
        if len(fetched) != len(RULE_FILES):
            warnings.append("未能获取全部上游规则，未写入规则快照")
            return errors, warnings
        commit = "unknown"
        try:
            payload = json.loads(_fetch(COMMIT_API, timeout=timeout))
            commit = str(payload.get("sha") or "unknown")
        except Exception as exc:  # noqa: BLE001 - commit is best effort
            warnings.append(f"无法获取上游 commit: {exc}")
        lock = {
            "repo": UPSTREAM_REPO,
            "commit": commit,
            "fetched_at": date.today().isoformat(),
            "files": {
                rel: hashlib.sha256(data).hexdigest()
                for rel, data in fetched.items()
            },
        }
        try:
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            lock_path.write_text(
                json.dumps(lock, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            errors.append(f"无法写入规则快照 {lock_path}: {exc}")
        return errors, warnings

    if not lock_path.is_file():
        warnings.append(
            f"规则快照不存在: {lock_path}（运行 --write-lock 生成）"
        )
        return errors, warnings
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"无法读取规则快照 {lock_path}: {exc}")
        return errors, warnings

    locked_files = lock.get("files") or {}
    for rel, data in fetched.items():
        expected = locked_files.get(rel)
        actual = hashlib.sha256(data).hexdigest()
        if expected is None:
            warnings.append(
                f"规则快照缺少 {rel}（上游新增文件，需要更新技能）"
            )
        elif expected != actual:
            warnings.append(f"上游规则已变化，需要复核: {rel}")
    return errors, warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="xime-index checkout")
    parser.add_argument(
        "--type",
        choices=["layout", "plugin-v2", "plugin-v1", "rime", "model"],
    )
    parser.add_argument("--check-rules", action="store_true")
    parser.add_argument("--write-lock", action="store_true")
    parser.add_argument("--lock", help="rule snapshot path (default: references/)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    repo = Path(args.repo)
    details = check_tool_details()
    tools = {name: info.path for name, info in details.items()}
    errors, warnings = check_repo(repo)

    for tool in REQUIRED_TOOLS:
        if not tools.get(tool):
            errors.append(f"缺少必需工具: {tool}")

    notes: list[str] = []
    for tool, hint in OPTIONAL_TOOL_HINTS.items():
        if tool == "gh":
            continue  # gh has extra state, handled below
        if not details[tool].found:
            notes.append(f"未找到可选工具 {tool}（{hint}）")

    gh_info = details["gh"]
    gh_auth = check_gh_auth(gh_info.path)
    gh_notes: list[str] = []
    if gh_info.found:
        if not gh_info.on_path:
            gh_notes.append(
                f"不在 PATH：{gh_info.path}（调用时用绝对路径，或把该目录加入 PATH）"
            )
        gh_notes.extend(_gh_auth_notes(gh_auth))
    else:
        gh_notes.append(
            f"未找到（{OPTIONAL_TOOL_HINTS['gh']}）。安装方式：{gh_install_hint()}；"
            "也可从 https://github.com/cli/cli/releases 下载。"
            "是否安装请先询问用户，不要自动安装。"
        )

    if args.check_rules or args.write_lock:
        rule_errors, rule_warnings = check_rules(
            repo,
            write_lock=args.write_lock,
            lock_path=Path(args.lock) if args.lock else None,
        )
        errors.extend(rule_errors)
        warnings.extend(rule_warnings)
        if args.write_lock and not rule_errors:
            notes.append("规则快照已写入（--write-lock）")

    report = {
        "repo": str(repo),
        "type": args.type,
        "tools": tools,
        "gh": {
            "path": gh_info.path,
            "source": gh_info.source,
            "state": gh_auth.state,
            "account": gh_auth.account,
            "scopes": list(gh_auth.scopes),
            "missingScopes": list(gh_auth.missing_scopes),
            "viaEnvToken": gh_auth.via_env_token,
            "notes": gh_notes,
        },
        "errors": errors,
        "warnings": warnings,
        "notes": notes,
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"repo: {repo}")
        if args.type:
            print(f"type: {args.type}")
        print("tools:")
        for tool in TOOLS:
            info = details[tool]
            if info.found and not info.on_path:
                print(f"  {tool}: {info.path} (不在 PATH)")
            else:
                print(f"  {tool}: {info.path or '(missing)'}")
        for note in gh_notes:
            print(f"gh:      {note}")
        for note in notes:
            print(f"note:    {note}")
        for warning in warnings:
            print(f"warning: {warning}")
        for error in errors:
            print(f"error:   {error}")
        print(
            f"{'OK' if not errors else 'FAILED'}: "
            f"{len(errors)} error(s), {len(warnings)} warning(s)"
        )

    if errors:
        return 2
    if warnings:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
