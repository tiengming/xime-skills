import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from tests.helpers import SKILL_ROOT

sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from preflight import (  # noqa: E402
    RULE_FILES,
    check_repo,
    check_rules,
    check_tools,
    main as preflight_main,
)

DEFAULT_RULES = {
    "CONTRIBUTING.md": b"# contributing\n",
    "LAYOUT_SPEC.md": b"# layout spec\n",
    "scripts/ci-update.py": b"#!/usr/bin/env python3\n",
    "scripts/lib.py": b"# lib\n",
}
COMMIT_SHA = "a" * 40


class FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


def fake_urlopen_factory(rules):
    def fake(request, timeout=None):
        url = request.full_url
        if "api.github.com" in url:
            return FakeResponse(json.dumps({"sha": COMMIT_SHA}).encode())
        for rel, payload in rules.items():
            if url.endswith("/main/" + rel):
                return FakeResponse(payload)
        raise AssertionError(f"unexpected url: {url}")

    return fake


def all_tools(name):
    return f"/usr/bin/{name}"


def optional_tools_missing(name):
    return None if name in {"gh", "uv", "npx"} else f"/usr/bin/{name}"


class PreflightTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.lock_path = self.tmp / "upstream.lock.json"

    def make_repo(self, with_src=True, with_upstream=True):
        repo = self.tmp / "xime-index"
        (repo / "scripts").mkdir(parents=True)
        (repo / "scripts" / "ci-update.py").write_text("", encoding="utf-8")
        (repo / "CONTRIBUTING.md").write_text("", encoding="utf-8")
        (repo / "LAYOUT_SPEC.md").write_text("", encoding="utf-8")
        if with_src:
            (repo / "src").mkdir()
        (repo / ".git").mkdir()
        config = "[core]\n\tbare = false\n"
        if with_upstream:
            config += (
                '[remote "upstream"]\n'
                "\turl = https://github.com/ximeiorg/xime-index.git\n"
                "\tfetch = +refs/heads/*:refs/remotes/upstream/*\n"
            )
        (repo / ".git" / "config").write_text(config, encoding="utf-8")
        return repo

    def test_check_tools_marks_optional_missing(self):
        with mock.patch("shutil.which", side_effect=optional_tools_missing):
            tools = check_tools()
        self.assertEqual(tools["python3"], "/usr/bin/python3")
        self.assertIsNone(tools["gh"])
        self.assertIsNone(tools["uv"])

    def test_complete_repo_without_optional_tools_exits_zero(self):
        repo = self.make_repo()
        out = io.StringIO()
        with mock.patch("shutil.which", side_effect=optional_tools_missing):
            with contextlib.redirect_stdout(out):
                rc = preflight_main(["--repo", str(repo)])
        self.assertEqual(rc, 0)
        self.assertIn("gh", out.getvalue())

    def test_missing_src_exits_two(self):
        repo = self.make_repo(with_src=False)
        with mock.patch("shutil.which", side_effect=all_tools):
            with contextlib.redirect_stdout(io.StringIO()):
                rc = preflight_main(["--repo", str(repo)])
        self.assertEqual(rc, 2)

    def test_missing_upstream_remote_is_warning(self):
        repo = self.make_repo(with_upstream=False)
        errors, warnings = check_repo(repo)
        self.assertEqual(errors, [])
        self.assertTrue(any("upstream" in w for w in warnings))

    def test_matching_lock_has_no_warnings(self):
        repo = self.make_repo()
        with mock.patch(
            "urllib.request.urlopen", side_effect=fake_urlopen_factory(DEFAULT_RULES)
        ):
            errors, warnings = check_rules(
                repo, write_lock=True, lock_path=self.lock_path
            )
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

        with mock.patch(
            "urllib.request.urlopen", side_effect=fake_urlopen_factory(DEFAULT_RULES)
        ):
            errors, warnings = check_rules(repo, lock_path=self.lock_path)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_changed_layout_spec_warns_and_exits_three(self):
        repo = self.make_repo()
        with mock.patch(
            "urllib.request.urlopen", side_effect=fake_urlopen_factory(DEFAULT_RULES)
        ):
            check_rules(repo, write_lock=True, lock_path=self.lock_path)

        changed = dict(DEFAULT_RULES)
        changed["LAYOUT_SPEC.md"] = b"# layout spec v2\n"
        out = io.StringIO()
        with mock.patch(
            "urllib.request.urlopen", side_effect=fake_urlopen_factory(changed)
        ), mock.patch("shutil.which", side_effect=all_tools):
            with contextlib.redirect_stdout(out):
                rc = preflight_main(
                    [
                        "--repo",
                        str(repo),
                        "--check-rules",
                        "--lock",
                        str(self.lock_path),
                    ]
                )
        self.assertEqual(rc, 3)
        self.assertIn("LAYOUT_SPEC.md", out.getvalue())

    def test_write_lock_writes_hashes_and_commit(self):
        repo = self.make_repo()
        with mock.patch(
            "urllib.request.urlopen", side_effect=fake_urlopen_factory(DEFAULT_RULES)
        ):
            errors, warnings = check_rules(
                repo, write_lock=True, lock_path=self.lock_path
            )
        self.assertEqual(errors, [])
        lock = json.loads(self.lock_path.read_text(encoding="utf-8"))
        self.assertEqual(lock["repo"], "ximeiorg/xime-index")
        self.assertEqual(lock["commit"], COMMIT_SHA)
        self.assertTrue(lock["fetched_at"])
        self.assertEqual(set(lock["files"]), set(RULE_FILES))
        for rel, payload in DEFAULT_RULES.items():
            self.assertEqual(
                lock["files"][rel], hashlib.sha256(payload).hexdigest()
            )

    def test_network_failure_warns_not_crash(self):
        repo = self.make_repo()
        with mock.patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("no network"),
        ):
            errors, warnings = check_rules(repo, lock_path=self.lock_path)
        self.assertEqual(errors, [])
        self.assertTrue(warnings)

    def test_missing_required_tool_is_error(self):
        repo = self.make_repo()

        def which(name):
            return None if name == "git" else f"/usr/bin/{name}"

        with mock.patch("shutil.which", side_effect=which):
            with contextlib.redirect_stdout(io.StringIO()):
                rc = preflight_main(["--repo", str(repo)])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
