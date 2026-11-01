"""Cross-platform tool discovery and GitHub CLI status checks.

`shutil.which` only looks at ``PATH``. On Windows, macOS and Linux the
GitHub CLI is frequently installed somewhere that is not on the PATH of the
process running the skill (``~/.local/bin``, ``%LOCALAPPDATA%\\Programs``,
``/opt/homebrew/bin`` ...), which used to look like "gh is not installed".
This module adds a bounded fallback search and reports whether the binary was
actually found on ``PATH``.

It also inspects ``gh auth status`` so the skill can tell apart "not installed"
from "installed but not logged in" and "logged in but missing scopes".

Nothing here prints or returns tokens: only account names and scope names are
extracted from the command output.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

_TOOL_NAMES = ("python3", "git", "curl", "gh", "uv", "npx")

_RE_ACCOUNT = re.compile(r"Logged in to github\.com account (\S+)", re.IGNORECASE)
_RE_SCOPES = re.compile(r"Token scopes: (.+)", re.IGNORECASE)
_RE_MISSING_SCOPES = re.compile(
    r"Missing required token scopes: (.+)", re.IGNORECASE
)
_RE_UNKNOWN_FLAG = re.compile(r"unknown (flag|shorthand)", re.IGNORECASE)
_RE_NOT_LOGGED_IN = re.compile(
    r"not logged into any GitHub hosts|You are not logged into any GitHub hosts",
    re.IGNORECASE,
)


def _env_get(env, key: str) -> str | None:
    """Read an env var case-insensitively (Windows uses LocalAppData, etc.)."""
    if key in env:
        return env[key]
    lowered = key.lower()
    for name, value in env.items():
        if name.lower() == lowered:
            return value
    return None


@dataclass(frozen=True)
class ToolInfo:
    """Result of looking up one executable."""

    name: str
    path: str | None
    source: str  # "PATH" | "fallback" | "missing"

    @property
    def found(self) -> bool:
        return self.path is not None

    @property
    def on_path(self) -> bool:
        return self.source == "PATH"


@dataclass(frozen=True)
class GhAuth:
    """Parsed `gh auth status` result without any token material."""

    state: str  # "missing" | "not-installed" | "not-authenticated" | "authenticated" | "unavailable"
    account: str | None = None
    scopes: tuple[str, ...] = ()
    missing_scopes: tuple[str, ...] = ()
    via_env_token: bool = False
    detail: str = ""


def default_search_dirs(
    *,
    platform: str | None = None,
    env: dict[str, str] | None = None,
    home: Path | str | None = None,
) -> list[Path]:
    """Return well-known install directories for the current platform."""
    platform = sys.platform if platform is None else platform
    env = os.environ if env is None else env
    home = Path(home) if home is not None else Path.home()

    dirs: list[Path] = [home / ".local" / "bin", home / "bin"]

    if platform.startswith("win"):
        local = _env_get(env, "LOCALAPPDATA")
        if local:
            dirs.append(Path(local) / "Programs" / "GitHub CLI")
            dirs.append(Path(local) / "Microsoft" / "WinGet" / "Links")
        for key in ("ProgramFiles", "ProgramFiles(x86)"):
            base = _env_get(env, key)
            if base:
                dirs.append(Path(base) / "GitHub CLI")
        scoop = _env_get(env, "SCOOP")
        dirs.append(Path(scoop) / "shims" if scoop else home / "scoop" / "shims")
        choco = _env_get(env, "ChocolateyInstall")
        dirs.append(
            Path(choco) / "bin" if choco else Path("C:/ProgramData/chocolatey/bin")
        )
    elif platform == "darwin":
        dirs.extend(
            [Path("/opt/homebrew/bin"), Path("/usr/local/bin"), Path("/opt/local/bin")]
        )
    else:
        dirs.extend(
            [
                Path("/usr/local/bin"),
                Path("/usr/bin"),
                Path("/snap/bin"),
                Path("/home/linuxbrew/.linuxbrew/bin"),
                home / ".linuxbrew" / "bin",
                Path("/nix/var/nix/profiles/default/bin"),
            ]
        )

    unique: list[Path] = []
    for directory in dirs:
        if directory not in unique:
            unique.append(directory)
    return unique


def resolve_tool(
    name: str,
    *,
    env: dict[str, str] | None = None,
    platform: str | None = None,
    home: Path | str | None = None,
    search_dirs: list[Path] | None = None,
    which=None,
) -> ToolInfo:
    """Locate *name* on PATH first, then in common install directories."""
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    which = shutil.which if which is None else which

    on_path = which(name, path=_env_get(env, "PATH"))
    if on_path:
        return ToolInfo(name=name, path=on_path, source="PATH")

    exe = f"{name}.exe" if platform.startswith("win") else name
    dirs = (
        default_search_dirs(platform=platform, env=env, home=home)
        if search_dirs is None
        else search_dirs
    )
    for directory in dirs:
        candidate = Path(directory) / exe
        try:
            if candidate.is_file():
                return ToolInfo(name=name, path=str(candidate), source="fallback")
        except OSError:
            continue
    return ToolInfo(name=name, path=None, source="missing")


def resolve_tools(
    names: tuple[str, ...] = _TOOL_NAMES, **kwargs
) -> dict[str, ToolInfo]:
    return {name: resolve_tool(name, **kwargs) for name in names}


def _split_scopes(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    return tuple(
        part.strip().strip("'\"").strip()
        for part in raw.split(",")
        if part.strip().strip("'\"").strip()
    )


def check_gh_auth(
    path: str | None,
    *,
    run=subprocess.run,
    timeout: int = 15,
    env: dict[str, str] | None = None,
) -> GhAuth:
    """Run `gh auth status` and return a token-free summary."""
    if not path:
        return GhAuth(state="not-installed")

    base = [path, "auth", "status", "--hostname", "github.com"]
    completed = None
    try:
        completed = run(
            base,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=os.environ if env is None else env,
        )
        output = "\n".join(
            part for part in (completed.stdout, completed.stderr) if part
        )
        if completed.returncode != 0 and _RE_UNKNOWN_FLAG.search(output):
            completed = run(
                [path, "auth", "status"],
                capture_output=True,
                text=True,
                timeout=timeout,
                env=os.environ if env is None else env,
            )
            output = "\n".join(
                part for part in (completed.stdout, completed.stderr) if part
            )
    except (OSError, subprocess.SubprocessError) as exc:
        return GhAuth(state="unavailable", detail=str(exc))

    if _RE_NOT_LOGGED_IN.search(output):
        return GhAuth(state="not-authenticated")

    account_match = _RE_ACCOUNT.search(output)
    if account_match:
        return GhAuth(
            state="authenticated",
            account=account_match.group(1),
            scopes=_split_scopes(
                _RE_SCOPES.search(output).group(1)
                if _RE_SCOPES.search(output)
                else None
            ),
            missing_scopes=_split_scopes(
                _RE_MISSING_SCOPES.search(output).group(1)
                if _RE_MISSING_SCOPES.search(output)
                else None
            ),
            via_env_token=bool(
                re.search(r"\b(?:GH_TOKEN|GITHUB_TOKEN)\b", output)
            ),
        )

    if completed.returncode == 0:
        return GhAuth(state="authenticated")

    return GhAuth(state="unavailable", detail=f"gh auth status 退出码 {completed.returncode}")


def gh_install_hint(platform: str | None = None) -> str:
    """Platform-appropriate install commands for the GitHub CLI."""
    platform = sys.platform if platform is None else platform
    if platform.startswith("win"):
        return "winget install --id GitHub.cli 或 scoop install gh"
    if platform == "darwin":
        return "brew install gh"
    return (
        "sudo apt install gh（Debian/Ubuntu）、sudo dnf install gh（Fedora）、"
        "sudo pacman -S github-cli（Arch）"
    )


@dataclass
class GhReport:
    """Everything the skill needs to know about the local gh setup."""

    tool: ToolInfo
    auth: GhAuth = field(default_factory=lambda: GhAuth(state="unavailable"))
    notes: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        blocking = {"repo"} & set(self.auth.missing_scopes)
        return self.auth.state == "authenticated" and not blocking
