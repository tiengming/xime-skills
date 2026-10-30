import contextlib
import hashlib
import io
import sys
import unittest

from tests.helpers import HTTPFixture, SKILL_ROOT

sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from asset_meta import build_meta, main as asset_main  # noqa: E402
from lib import classify_url, github_compare_url, human_size  # noqa: E402


class AssetMetaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http = HTTPFixture().start()
        cls.base = cls.http.base_url

    @classmethod
    def tearDownClass(cls):
        cls.http.stop()

    def test_sha256_and_size(self):
        meta = build_meta(f"{self.base}/asset.bin", timeout=5)
        self.assertEqual(meta["sha256"], hashlib.sha256(b"xime" * 1000).hexdigest())
        self.assertEqual(meta["sizeBytes"], 4000)
        self.assertEqual(meta["size"], "3.9 KB")

    def test_human_size(self):
        self.assertEqual(human_size(0), "0 B")
        self.assertEqual(human_size(4000), "3.9 KB")
        self.assertEqual(human_size(1024 * 1024), "1.0 MB")
        self.assertEqual(human_size(1024 * 1024 * 1024), "1.00 GB")

    def test_release_url_is_policy_ok(self):
        kind, immutable, policy_ok, _ = classify_url(
            "https://github.com/o/r/releases/download/v1.0.0/x.zip"
        )
        self.assertEqual(kind, "github-release")
        self.assertTrue(immutable)
        self.assertTrue(policy_ok)

    def test_branch_raw_url_is_not_policy_ok(self):
        kind, immutable, policy_ok, warnings = classify_url(
            "https://raw.githubusercontent.com/o/r/main/x.zip"
        )
        self.assertFalse(immutable)
        self.assertFalse(policy_ok)
        self.assertTrue(warnings)

    def test_pinned_raw_commit_is_immutable_but_not_policy_ok(self):
        kind, immutable, policy_ok, _ = classify_url(
            "https://raw.githubusercontent.com/o/r/"
            "0123456789abcdef0123456789abcdef01234567/x.zip"
        )
        self.assertEqual(kind, "github-raw-commit")
        self.assertTrue(immutable)
        self.assertFalse(policy_ok)

    def test_jsdelivr_tag_is_immutable_but_not_policy_ok(self):
        kind, immutable, policy_ok, _ = classify_url(
            "https://cdn.jsdelivr.net/gh/o/r@v1.0.0/x.zip"
        )
        self.assertEqual(kind, "jsdelivr-tag")
        self.assertTrue(immutable)
        self.assertFalse(policy_ok)

    def test_jsdelivr_branch_is_mutable(self):
        _, immutable, policy_ok, _ = classify_url(
            "https://cdn.jsdelivr.net/gh/o/r@main/x.zip"
        )
        self.assertFalse(immutable)
        self.assertFalse(policy_ok)

    def test_redirect_is_followed(self):
        meta = build_meta(f"{self.base}/redirect", timeout=5)
        self.assertEqual(meta["sha256"], hashlib.sha256(b"xime" * 1000).hexdigest())

    def test_404_returns_2(self):
        with contextlib.redirect_stderr(io.StringIO()):
            rc = asset_main([f"{self.base}/missing", "--timeout", "5"])
        self.assertEqual(rc, 2)

    def test_timeout_returns_2(self):
        with contextlib.redirect_stderr(io.StringIO()):
            rc = asset_main([f"{self.base}/slow", "--timeout", "1"])
        self.assertEqual(rc, 2)

    def test_expected_sha_mismatch_returns_4(self):
        with contextlib.redirect_stderr(io.StringIO()):
            rc = asset_main(
                [
                    f"{self.base}/asset.bin",
                    "--timeout",
                    "5",
                    "--expected-sha256",
                    "0" * 64,
                ]
            )
        self.assertEqual(rc, 4)

    def test_json_output_contains_policy_fields(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = asset_main([f"{self.base}/asset.bin", "--timeout", "5", "--json"])
        self.assertEqual(rc, 0)
        self.assertIn('"policy_ok"', out.getvalue())

    def test_github_compare_url(self):
        url = github_compare_url(
            "ximeiorg/xime-index", "tester", "submit/layout/demo-1.0.0"
        )
        self.assertEqual(
            url,
            "https://github.com/ximeiorg/xime-index/compare/main..."
            "tester:submit/layout/demo-1.0.0?expand=1",
        )


if __name__ == "__main__":
    unittest.main()
