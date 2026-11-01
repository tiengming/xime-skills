import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import SKILL_ROOT

sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from tools import (  # noqa: E402
    check_gh_auth,
    default_search_dirs,
    gh_install_hint,
    resolve_tool,
)


def fake_which_found(name, path=None):
    return f"/usr/bin/{name}"


def fake_which_missing(name, path=None):
    return None


class FakeCompleted:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class ToolSearchDirsTest(unittest.TestCase):
    def test_linux_includes_user_local_bin(self):
        dirs = default_search_dirs(
            platform="linux", env={}, home=Path("/home/tester")
        )
        self.assertIn(Path("/home/tester/.local/bin"), dirs)
        self.assertIn(Path("/usr/local/bin"), dirs)
        self.assertIn(Path("/snap/bin"), dirs)

    def test_macos_prefers_homebrew(self):
        dirs = default_search_dirs(platform="darwin", env={}, home=Path("/Users/t"))
        self.assertEqual(dirs[2], Path("/opt/homebrew/bin"))
        self.assertIn(Path("/usr/local/bin"), dirs)

    def test_windows_uses_localappdata_and_programfiles(self):
        env = {
            "LOCALAPPDATA": r"C:\Users\t\AppData\Local",
            "ProgramFiles": r"C:\Program Files",
            "SCOOP": r"C:\Users\t\scoop",
        }
        dirs = default_search_dirs(platform="win32", env=env, home=Path("C:/Users/t"))
        self.assertIn(
            Path(r"C:\Users\t\AppData\Local") / "Programs" / "GitHub CLI", dirs
        )
        self.assertIn(Path(r"C:\Program Files") / "GitHub CLI", dirs)
        self.assertIn(Path(r"C:\Users\t\scoop") / "shims", dirs)
        self.assertIn(
            Path(r"C:\Users\t\AppData\Local") / "Microsoft" / "WinGet" / "Links",
            dirs,
        )

    def test_windows_defaults_without_env(self):
        dirs = default_search_dirs(
            platform="win32", env={}, home=Path("C:/Users/t")
        )
        self.assertIn(Path("C:/Users/t/scoop/shims"), dirs)
        self.assertIn(Path("C:/ProgramData/chocolatey/bin"), dirs)

    def test_windows_env_keys_are_case_insensitive(self):
        env = {"LocalAppData": r"C:\Users\t\AppData\Local"}
        dirs = default_search_dirs(
            platform="win32", env=env, home=Path("C:/Users/t")
        )
        self.assertIn(
            Path(r"C:\Users\t\AppData\Local") / "Programs" / "GitHub CLI", dirs
        )

    def test_dirs_are_unique(self):
        dirs = default_search_dirs(
            platform="linux", env={}, home=Path("/home/tester")
        )
        self.assertEqual(len(dirs), len(set(dirs)))


class ResolveToolTest(unittest.TestCase):
    def test_found_on_path(self):
        info = resolve_tool(
            "gh",
            env={"PATH": "/usr/bin"},
            platform="linux",
            which=fake_which_found,
            search_dirs=[],
        )
        self.assertTrue(info.found)
        self.assertTrue(info.on_path)
        self.assertEqual(info.source, "PATH")

    def test_found_outside_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            exe = bin_dir / "gh"
            exe.write_text("#!/bin/sh\n", encoding="utf-8")
            info = resolve_tool(
                "gh",
                env={"PATH": ""},
                platform="linux",
                which=fake_which_missing,
                search_dirs=[bin_dir],
            )
        self.assertTrue(info.found)
        self.assertFalse(info.on_path)
        self.assertEqual(info.source, "fallback")
        self.assertTrue(info.path.endswith("gh"))

    def test_windows_uses_exe_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            (bin_dir / "gh.exe").write_text("", encoding="utf-8")
            info = resolve_tool(
                "gh",
                env={"PATH": ""},
                platform="win32",
                which=fake_which_missing,
                search_dirs=[bin_dir],
            )
        self.assertTrue(info.found)
        self.assertTrue(info.path.endswith("gh.exe"))

    def test_missing_everywhere(self):
        info = resolve_tool(
            "gh",
            env={"PATH": ""},
            platform="linux",
            which=fake_which_missing,
            search_dirs=[Path("/nonexistent-dir")],
        )
        self.assertFalse(info.found)
        self.assertEqual(info.source, "missing")


class GhAuthTest(unittest.TestCase):
    def run_with(self, stdout="", stderr="", returncode=0):
        calls = []

        def fake_run(args, **kwargs):
            calls.append(args)
            return FakeCompleted(stdout, stderr, returncode)

        auth = check_gh_auth("/usr/bin/gh", run=fake_run, env={})
        return auth, calls

    def test_missing_binary(self):
        auth = check_gh_auth(None)
        self.assertEqual(auth.state, "not-installed")

    def test_authenticated_with_scopes(self):
        auth, _ = self.run_with(
            stdout=(
                "github.com\n"
                "  ✓ Logged in to github.com account tester (keyring)\n"
                "  - Token scopes: 'repo', 'workflow'\n"
            )
        )
        self.assertEqual(auth.state, "authenticated")
        self.assertEqual(auth.account, "tester")
        self.assertEqual(auth.scopes, ("repo", "workflow"))
        self.assertEqual(auth.missing_scopes, ())

    def test_authenticated_with_missing_scopes(self):
        auth, _ = self.run_with(
            stdout=(
                "github.com\n"
                "  ✓ Logged in to github.com account tester (GH_TOKEN)\n"
                "  - Token scopes: 'repo'\n"
                "  ! Missing required token scopes: 'read:org'\n"
            ),
            returncode=1,
        )
        self.assertEqual(auth.state, "authenticated")
        self.assertEqual(auth.missing_scopes, ("read:org",))
        self.assertTrue(auth.via_env_token)

    def test_not_authenticated(self):
        auth, _ = self.run_with(
            stderr="You are not logged into any GitHub hosts.",
            returncode=1,
        )
        self.assertEqual(auth.state, "not-authenticated")

    def test_unknown_hostname_flag_retries_plain_status(self):
        calls = []

        def fake_run(args, **kwargs):
            calls.append(args)
            if "--hostname" in args:
                return FakeCompleted(stderr="unknown flag: --hostname", returncode=1)
            return FakeCompleted(
                stdout="Logged in to github.com account tester (keyring)\n"
            )

        auth = check_gh_auth("/usr/bin/gh", run=fake_run, env={})
        self.assertEqual(auth.state, "authenticated")
        self.assertEqual(len(calls), 2)
        self.assertNotIn("--hostname", calls[1])

    def test_command_failure_is_unavailable(self):
        def fake_run(args, **kwargs):
            raise subprocess.TimeoutExpired(cmd=args, timeout=5)

        auth = check_gh_auth("/usr/bin/gh", run=fake_run, env={})
        self.assertEqual(auth.state, "unavailable")

    def test_output_never_carries_tokens(self):
        secret = "ghp_" + "A" * 36
        auth, _ = self.run_with(
            stdout=(
                "github.com\n"
                "  ✓ Logged in to github.com account tester (keyring)\n"
                f"  - Token: {secret}\n"
                "  - Token scopes: 'repo'\n"
            )
        )
        rendered = repr(auth)
        self.assertNotIn(secret, rendered)
        self.assertNotIn("ghp_", rendered)


class InstallHintTest(unittest.TestCase):
    def test_windows_hint(self):
        self.assertIn("winget", gh_install_hint("win32"))

    def test_macos_hint(self):
        self.assertIn("brew", gh_install_hint("darwin"))

    def test_linux_hint_mentions_package_managers(self):
        hint = gh_install_hint("linux")
        self.assertIn("apt", hint)
        self.assertIn("dnf", hint)


if __name__ == "__main__":
    unittest.main()
