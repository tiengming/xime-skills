#!/usr/bin/env python3
"""Validate one xime-index entry YAML file.

Usage:
  python3 scripts/validate_entry.py <entry.yaml> [--repo-root DIR]
      [--asset-file PACKAGE] [--check-urls] [--json]

Exit codes: 0 pass, 1 validation errors, 2 usage/file error, 3 warnings only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import USER_AGENT, classify_url  # noqa: E402

HEX64_RE = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

TYPE_BY_DIR = {
    "layouts": "layout",
    "rimes": "rime",
    "models": "model",
    "plugins/v1": "plugin-v1",
    "plugins/v2": "plugin-v2",
}

COMMON_FIELDS = {
    "id",
    "name",
    "author",
    "description",
    "tags",
    "homepage",
    "license",
    "appVersion",
    "warning",
    "currentVersion",
    "versions",
}

ALLOWED_FIELDS = {
    "layout": COMMON_FIELDS
    | {"repo", "requiresSchemes", "screenshots"},
    "rime": COMMON_FIELDS | {"type", "dependencies"},
    "model": COMMON_FIELDS | {"category", "size", "type"},
    "plugin-v1": COMMON_FIELDS | {"type", "pluginType"},
    "plugin-v2": COMMON_FIELDS
    | {
        "type",
        "pluginType",
        "icon",
        "activation",
        "minHostVersion",
        "platforms",
        "capabilities",
        "network",
    },
}

COMMON_REQUIRED = ["id", "name", "author", "description", "currentVersion", "versions"]

REQUIRED_FIELDS = {
    "layout": COMMON_REQUIRED + ["tags", "repo", "license", "appVersion"],
    "rime": COMMON_REQUIRED + ["type", "tags", "appVersion"],
    "model": COMMON_REQUIRED + ["category", "size", "type"],
    "plugin-v1": COMMON_REQUIRED + ["type", "tags", "pluginType"],
    "plugin-v2": COMMON_REQUIRED + ["type", "tags", "pluginType"],
}

ROOT_DOCS = {
    "readme.md",
    "notice.md",
    "license",
    "license.md",
    "license.txt",
    "changelog.md",
}
ROOT_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
THEME_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
FONT_EXTS = {".ttf", ".otf"}


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    type: str = "unknown"
    id: str = ""

    @property
    def ok(self) -> bool:
        return not self.errors


def detect_type(path: Path) -> str:
    """Infer the entry type from its position under ``src/``."""
    normalized = path.as_posix().lower()
    for dirname, entry_type in TYPE_BY_DIR.items():
        if f"/{dirname}/" in normalized + "/" or normalized.endswith(f"/{dirname}"):
            return entry_type
    return "unknown"


def validate_zip(path: Path) -> tuple[list[str], list[str]]:
    """Check a layout/plugin package: paths, symlinks and allowed layout."""
    errors: list[str] = []
    warnings: list[str] = []
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        return [f"无法读取 zip: {exc}"], []

    with archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]

        has_root_manifest = False
        for info in infos:
            name = info.filename
            normalized = name.replace("\\", "/")
            if "\\" in name:
                errors.append(f"zip 路径不能包含反斜杠: {name}")
            if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
                errors.append(f"zip 路径不能是绝对路径: {name}")
            if ".." in Path(normalized).parts:
                errors.append(f"zip 路径不能包含 '..': {name}")
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                errors.append(f"zip 不能包含符号链接: {name}")
            if normalized == "xime.custom.yaml":
                has_root_manifest = True

        if not has_root_manifest:
            errors.append(
                "zip 根级必须包含 xime.custom.yaml（不能有顶层目录壳）"
            )

        for name in names:
            normalized = name.replace("\\", "/").lstrip("./")
            if not normalized or name.endswith("/"):
                continue
            parts = normalized.split("/")
            suffix = Path(normalized).suffix.lower()

            if len(parts) == 1:
                if parts[0] == "xime.custom.yaml":
                    continue
                if parts[0].lower() in ROOT_DOCS or suffix in ROOT_IMAGE_EXTS:
                    continue
                warnings.append(f"zip 根级文件不在预期内: {name}")
            elif parts[0] == "themes":
                if len(parts) != 2 or not parts[1] or suffix not in THEME_EXTS:
                    errors.append(
                        f"themes/ 只允许一层 png/jpg/jpeg/webp/gif 文件: {name}"
                    )
            elif parts[0] == "fonts":
                if len(parts) != 2 or not parts[1] or suffix not in FONT_EXTS:
                    errors.append(f"fonts/ 只允许一层 ttf/otf 文件: {name}")
            else:
                warnings.append(f"zip 包含未预期的目录: {name}")

    return errors, warnings


def probe_url(url: str, timeout: int = 15) -> tuple[int | None, str | None]:
    """GET a URL with a one-byte range; return (status, error)."""
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Range": "bytes=0-0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, None
    except urllib.error.HTTPError as exc:
        try:
            exc.close()
        except Exception:  # noqa: BLE001 - best effort cleanup
            pass
        return exc.code, str(exc)
    except Exception as exc:  # noqa: BLE001 - network errors are warnings
        return None, str(exc)


def _check_fields(report: Report, data: dict[str, Any]) -> None:
    allowed = ALLOWED_FIELDS.get(report.type, set())
    tags = data.get("tags") if isinstance(data.get("tags"), list) else []
    for key in data:
        if key in allowed:
            continue
        if key == "color_schemes" and report.type == "layout" and "配色" in tags:
            continue
        report.warnings.append(
            f"未知字段 {key!r}（xime-index 只读取白名单字段；确认是否应写进条目）"
        )

    for key in REQUIRED_FIELDS.get(report.type, COMMON_REQUIRED):
        value = data.get(key)
        if value is None or value == "" or value == [] or value == {}:
            report.errors.append(f"缺少必填字段: {key}")


def _check_versions_common(report: Report, data: dict[str, Any]) -> None:
    versions = data.get("versions")
    if not isinstance(versions, list) or not versions:
        report.errors.append("versions 必须是非空列表")
        return

    seen: set[str] = set()
    for index, version in enumerate(versions):
        if not isinstance(version, dict):
            report.errors.append(f"versions[{index}] 必须是映射")
            continue
        label = str(version.get("version") or f"#{index}")
        for key in ("version", "date", "changelog"):
            if key not in version:
                report.errors.append(f"版本 {label}: 缺少 {key}")
        raw_version = version.get("version")
        if isinstance(raw_version, str):
            if raw_version in seen:
                report.errors.append(f"duplicate version: {raw_version}")
            seen.add(raw_version)
        date_value = version.get("date")
        if date_value and not DATE_RE.match(str(date_value)):
            report.warnings.append(
                f"版本 {label}: date 建议使用 YYYY-MM-DD 格式，当前为 {date_value!r}"
            )
        changelog = version.get("changelog")
        if isinstance(changelog, str) and not changelog.strip():
            report.warnings.append(f"版本 {label}: changelog 为空")

    current = data.get("currentVersion")
    if current is not None and str(current) not in seen:
        report.errors.append(
            f"currentVersion {current!r} 不在 versions 中"
            "（更新版本时必须同步 currentVersion）"
        )


def _check_screenshot(report: Report, url: Any) -> None:
    if not isinstance(url, str) or not url.startswith("https://"):
        report.errors.append(f"screenshot 必须是 HTTPS URL: {url!r}")
        return
    kind, immutable, policy_ok, _ = classify_url(url)
    if kind == "other":
        report.warnings.append(
            f"screenshot 无法确认是否固定到 tag/commit: {url}"
        )
        return
    if not immutable:
        report.errors.append(
            f"screenshot 必须固定到 tag/commit，不能使用分支: {url}"
        )
        return
    if not policy_ok:
        report.warnings.append(
            f"screenshot 使用 {kind}（jsDelivr/raw 等非 Release 地址），"
            f"已固定但建议改用 GitHub Release 附件: {url}"
        )


def _check_download_item(
    report: Report,
    label: str,
    item: Any,
    *,
    current: bool,
    context: str = "downloadUrl",
) -> None:
    if not isinstance(item, dict):
        report.errors.append(f"版本 {label}: {context} 项必须是映射")
        return

    url = item.get("url")
    if not isinstance(url, str) or not url:
        report.errors.append(f"版本 {label}: {context} 缺少 url")
    elif not url.startswith("https://"):
        report.errors.append(f"版本 {label}: {context} 必须使用 HTTPS: {url}")
    else:
        kind, immutable, policy_ok, _ = classify_url(url)
        if current and not policy_ok:
            report.errors.append(
                f"版本 {label}: {context} not an immutable Release asset: {url}"
            )
        elif not current and not policy_ok:
            report.warnings.append(
                f"历史版本 {label}: {context} 不是 Release 附件"
                f"（历史保留；新版本必须用 Release 附件）: {url}"
            )

    sha256 = item.get("sha256")
    if not sha256:
        report.errors.append(f"版本 {label}: {context} 缺少 sha256")
    elif not HEX64_RE.match(str(sha256)):
        report.errors.append(
            f"版本 {label}: {context} sha256 必须是 64 位十六进制"
        )

    size = item.get("size")
    if not size:
        report.errors.append(f"版本 {label}: {context} 缺少 size")

    if "sizeBytes" not in item:
        report.warnings.append(
            f"版本 {label}: {context} 建议补充 sizeBytes（商店显示与排序用）"
        )
    else:
        size_bytes = item["sizeBytes"]
        if not isinstance(size_bytes, int) or isinstance(size_bytes, bool):
            report.errors.append(f"版本 {label}: {context} sizeBytes 必须是整数")
        elif size_bytes <= 0:
            report.errors.append(f"版本 {label}: {context} sizeBytes 必须为正整数")


def validate_layout(
    report: Report,
    data: dict[str, Any],
    *,
    asset_file: Path | None = None,
) -> None:
    repo = data.get("repo")
    if repo and not str(repo).startswith("https://"):
        report.errors.append(f"repo 必须是 HTTPS URL: {repo}")

    app_version = data.get("appVersion")
    if app_version and not str(app_version).startswith(">="):
        report.errors.append(f"appVersion 必须以 >= 开头: {app_version}")

    requires = data.get("requiresSchemes")
    if requires is not None and not isinstance(requires, list):
        report.errors.append("requiresSchemes 必须是列表")

    if "xime_index" in data:
        report.warnings.append(
            "索引条目里不应包含 xime_index（那是 xime.custom.yaml 的配置）"
        )
    style = data.get("style")
    if isinstance(style, dict) and "color_scheme" in style:
        report.warnings.append(
            "索引条目里不应包含 style.color_scheme（那是 xime.custom.yaml 的配置）"
        )

    screenshots = data.get("screenshots")
    if not isinstance(screenshots, list) or not screenshots:
        report.errors.append("screenshots 必须包含 1~5 张图片")
    else:
        if len(screenshots) > 5:
            report.errors.append(
                f"screenshots 最多 5 张，当前为 {len(screenshots)} 张"
            )
        for url in screenshots:
            _check_screenshot(report, url)

    current_version = str(data.get("currentVersion"))
    versions = data.get("versions")
    if isinstance(versions, list):
        for version in versions:
            if not isinstance(version, dict):
                continue
            label = str(version.get("version"))
            is_current = label == current_version
            download_urls = version.get("downloadUrl")
            if not isinstance(download_urls, list) or not download_urls:
                report.errors.append(f"版本 {label}: downloadUrl 必须是非空列表")
                continue
            for item in download_urls:
                _check_download_item(
                    report, label, item, current=is_current, context="downloadUrl"
                )

    if asset_file is not None:
        zip_errors, zip_warnings = validate_zip(asset_file)
        report.errors.extend(zip_errors)
        report.warnings.extend(zip_warnings)


def _check_all_urls(report: Report, data: dict[str, Any]) -> None:
    urls: list[str] = []
    screenshots = data.get("screenshots")
    if isinstance(screenshots, list):
        urls.extend(str(url) for url in screenshots)
    versions = data.get("versions")
    if isinstance(versions, list):
        for version in versions:
            if not isinstance(version, dict):
                continue
            for item in version.get("downloadUrl") or []:
                if isinstance(item, dict) and item.get("url"):
                    urls.append(str(item["url"]))

    seen: set[str] = set()
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        status, error = probe_url(url)
        if status in {403, 404}:
            report.errors.append(f"URL 无法访问（HTTP {status}）: {url}")
        elif status is None:
            report.warnings.append(f"URL 探测失败（网络错误）: {url} ({error})")
        elif status >= 400:
            report.warnings.append(f"URL 返回 HTTP {status}: {url}")


def validate(
    path: Path,
    repo_root: Path | None = None,
    asset_file: Path | None = None,
    check_urls: bool = False,
) -> Report:
    """Validate one entry file and return a Report."""
    path = Path(path)
    report = Report(type=detect_type(path))
    if not path.is_file():
        report.errors.append(f"文件不存在: {path}")
        return report

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        report.errors.append(f"无法解析 YAML: {exc}")
        return report

    if not isinstance(data, dict):
        report.errors.append("条目必须是 YAML 映射")
        return report

    report.id = str(data.get("id") or path.stem)
    if path.stem != report.id:
        report.errors.append(
            f"filename must equal id: 文件名为 {path.stem!r}，id 为 {report.id!r}"
        )

    _check_fields(report, data)
    _check_versions_common(report, data)

    if report.type == "layout":
        validate_layout(report, data, asset_file=asset_file)
    elif report.type in ALLOWED_FIELDS:
        report.warnings.append(
            f"{report.type} 类型的完整校验尚未实现（后续任务补充）"
        )

    if check_urls:
        _check_all_urls(report, data)

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="entry YAML file")
    parser.add_argument("--repo-root", help="path to the xime-index checkout")
    parser.add_argument("--asset-file", help="layout/plugin package to inspect")
    parser.add_argument("--check-urls", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    path = Path(args.path)
    if not path.is_file():
        print(f"error: 文件不存在: {path}", file=sys.stderr)
        return 2

    report = validate(
        path,
        repo_root=Path(args.repo_root) if args.repo_root else None,
        asset_file=Path(args.asset_file) if args.asset_file else None,
        check_urls=args.check_urls,
    )

    if args.json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    else:
        print(f"type: {report.type}")
        print(f"id:   {report.id or '-'}")
        for warning in report.warnings:
            print(f"warning: {warning}")
        for error in report.errors:
            print(f"error:   {error}")
        print(
            f"{'OK' if report.ok else 'FAILED'}: "
            f"{len(report.errors)} error(s), {len(report.warnings)} warning(s)"
        )

    if report.errors:
        return 1
    if report.warnings:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
