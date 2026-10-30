import contextlib
import copy
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import yaml

from tests.helpers import HTTPFixture, SKILL_ROOT

sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from validate_entry import (  # noqa: E402
    Report,
    detect_type,
    main as validate_main,
    probe_url,
    validate,
    validate_zip,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
VALID_LAYOUT = FIXTURES / "layout" / "valid.yaml"
HEX64 = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


def layout_data():
    return yaml.safe_load(VALID_LAYOUT.read_text(encoding="utf-8"))


class LayoutValidationTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "src" / "layouts").mkdir(parents=True)

    def write(self, data, filename="demo_layout.yaml"):
        path = self.root / "src" / "layouts" / filename
        path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
        return path

    def run_validate(self, data=None, filename="demo_layout.yaml", **kwargs):
        path = self.write(data if data is not None else layout_data(), filename)
        return validate(path, repo_root=self.root, **kwargs)

    def test_valid_fixture_has_no_errors(self):
        report = self.run_validate()
        self.assertIsInstance(report, Report)
        self.assertEqual(report.type, "layout")
        self.assertEqual(report.id, "demo_layout")
        self.assertEqual(report.errors, [])

    def test_pinned_jsdelivr_screenshot_warns_but_passes(self):
        report = self.run_validate()
        self.assertTrue(any("jsDelivr" in w for w in report.warnings))

    def test_missing_size_bytes_warns(self):
        report = self.run_validate()
        self.assertTrue(any("sizeBytes" in w for w in report.warnings))

    def test_filename_must_equal_id(self):
        report = self.run_validate(filename="wrong.yaml")
        self.assertTrue(any("filename must equal id" in e for e in report.errors))

    def test_missing_sha256_is_error(self):
        data = layout_data()
        del data["versions"][0]["downloadUrl"][0]["sha256"]
        report = self.run_validate(data)
        self.assertTrue(any("sha256" in e for e in report.errors))

    def test_short_sha256_is_error(self):
        data = layout_data()
        data["versions"][0]["downloadUrl"][0]["sha256"] = "abc"
        report = self.run_validate(data)
        self.assertTrue(any("sha256" in e for e in report.errors))

    def test_branch_url_is_rejected_for_current_version(self):
        data = layout_data()
        data["versions"][0]["downloadUrl"][0]["url"] = (
            "https://raw.githubusercontent.com/tester/demo-layout/main/xime.custom.yaml"
        )
        report = self.run_validate(data)
        self.assertTrue(
            any("not an immutable Release asset" in e for e in report.errors)
        )

    def test_empty_screenshots_is_error(self):
        data = layout_data()
        data["screenshots"] = []
        report = self.run_validate(data)
        self.assertTrue(any("screenshots" in e for e in report.errors))

    def test_six_screenshots_is_error(self):
        data = layout_data()
        data["screenshots"] = data["screenshots"] * 6
        report = self.run_validate(data)
        self.assertTrue(any("screenshots" in e for e in report.errors))

    def test_branch_screenshot_is_error(self):
        data = layout_data()
        data["screenshots"] = [
            "https://cdn.jsdelivr.net/gh/tester/demo-layout@main/01.png"
        ]
        report = self.run_validate(data)
        self.assertTrue(any("screenshot" in e.lower() for e in report.errors))

    def test_current_version_must_exist_in_versions(self):
        data = layout_data()
        data["currentVersion"] = "2.0.0"
        report = self.run_validate(data)
        self.assertTrue(any("currentVersion" in e for e in report.errors))

    def test_duplicate_version_is_error(self):
        data = layout_data()
        data["versions"].append(copy.deepcopy(data["versions"][0]))
        report = self.run_validate(data)
        self.assertTrue(any("duplicate" in e.lower() for e in report.errors))

    def test_unknown_field_warns(self):
        data = layout_data()
        data["color_schemes"] = {"a": {}}
        report = self.run_validate(data)
        self.assertTrue(any("color_schemes" in w for w in report.warnings))
        self.assertEqual(report.errors, [])

    def test_theme_pack_allows_color_schemes(self):
        data = layout_data()
        data["tags"] = ["布局", "配色"]
        data["color_schemes"] = {"a": {}}
        report = self.run_validate(data)
        self.assertFalse(any("color_schemes" in w for w in report.warnings))

    def test_old_version_may_keep_pinned_non_release_url(self):
        data = layout_data()
        data["versions"][0]["downloadUrl"][0]["url"] = (
            "https://cdn.jsdelivr.net/gh/tester/demo-layout@"
            "0123456789abcdef0123456789abcdef01234567/xime.custom.yaml"
        )
        data["currentVersion"] = "1.0.1"
        data["versions"].insert(
            0,
            {
                "version": "1.0.1",
                "date": "2026-10-30",
                "changelog": "new release",
                "downloadUrl": [
                    {
                        "url": "https://github.com/tester/demo-layout/releases/"
                        "download/v1.0.1/xime.custom.yaml",
                        "sha256": HEX64,
                        "size": "12.0 KB",
                    }
                ],
            },
        )
        report = self.run_validate(data)
        self.assertEqual(report.errors, [])
        self.assertTrue(any("1.0.0" in w for w in report.warnings))

    def test_xime_index_and_color_scheme_warn(self):
        data = layout_data()
        data["xime_index"] = {"base_urls": []}
        data["style"] = {"color_scheme": "x"}
        report = self.run_validate(data)
        self.assertTrue(any("xime_index" in w for w in report.warnings))
        self.assertTrue(any("color_scheme" in w for w in report.warnings))


class DetectTypeTest(unittest.TestCase):
    def test_detects_all_five_types(self):
        cases = {
            "src/layouts/a.yaml": "layout",
            "src/rimes/a.yaml": "rime",
            "src/models/a.yaml": "model",
            "src/plugins/v1/a.yaml": "plugin-v1",
            "src/plugins/v2/a.yaml": "plugin-v2",
        }
        for rel, expected in cases.items():
            with self.subTest(rel=rel):
                self.assertEqual(detect_type(Path("/repo") / rel), expected)

    def test_unknown_path(self):
        self.assertEqual(detect_type(Path("/repo/src/other/a.yaml")), "unknown")


class ZipSafetyTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def make_zip(self, entries):
        path = self.tmp / "pkg.zip"
        with zipfile.ZipFile(path, "w") as zf:
            for name, data in entries:
                zf.writestr(name, data)
        return path

    def test_valid_zip(self):
        path = self.make_zip(
            [
                ("xime.custom.yaml", "patch:\n"),
                ("themes/a.jpg", b"jpg"),
                ("fonts/a.ttf", b"ttf"),
                ("README.md", "docs"),
                ("NOTICE.md", "notice"),
            ]
        )
        errors, _ = validate_zip(path)
        self.assertEqual(errors, [])

    def test_top_level_directory_shell_is_rejected(self):
        path = self.make_zip([("demo/xime.custom.yaml", "patch:\n")])
        errors, _ = validate_zip(path)
        self.assertTrue(any("xime.custom.yaml" in e for e in errors))

    def test_traversal_is_rejected(self):
        path = self.make_zip(
            [
                ("xime.custom.yaml", "patch:\n"),
                ("../evil.txt", "x"),
            ]
        )
        errors, _ = validate_zip(path)
        self.assertTrue(any(".." in e for e in errors))

    def test_absolute_path_is_rejected(self):
        path = self.make_zip(
            [
                ("xime.custom.yaml", "patch:\n"),
                ("/etc/passwd", "x"),
            ]
        )
        errors, _ = validate_zip(path)
        self.assertTrue(any("绝对路径" in e for e in errors))

    def test_bad_extension_is_rejected(self):
        path = self.make_zip(
            [
                ("xime.custom.yaml", "patch:\n"),
                ("themes/a.exe", b"x"),
            ]
        )
        errors, _ = validate_zip(path)
        self.assertTrue(any(".exe" in e or "themes" in e for e in errors))

    def test_symlink_is_rejected(self):
        path = self.tmp / "symlink.zip"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("xime.custom.yaml", "patch:\n")
            info = zipfile.ZipInfo("themes/link.jpg")
            info.create_system = 3
            info.external_attr = 0o120777 << 16
            zf.writestr(info, "/etc/passwd")
        errors, _ = validate_zip(path)
        self.assertTrue(any("符号链接" in e for e in errors))


class UrlProbeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http = HTTPFixture().start()
        cls.base = cls.http.base_url

    @classmethod
    def tearDownClass(cls):
        cls.http.stop()

    def test_ok_status(self):
        status, error = probe_url(f"{self.base}/asset.bin", timeout=5)
        self.assertEqual(status, 200)
        self.assertIsNone(error)

    def test_missing_status(self):
        status, error = probe_url(f"{self.base}/missing", timeout=5)
        self.assertEqual(status, 404)
        self.assertIsNotNone(error)


class CliTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "src" / "layouts").mkdir(parents=True)
        self.path = self.root / "src" / "layouts" / "demo_layout.yaml"

    def write(self, data):
        self.path.write_text(
            yaml.safe_dump(data, allow_unicode=True), encoding="utf-8"
        )

    def test_clean_entry_exits_zero(self):
        data = layout_data()
        data["screenshots"] = [
            "https://github.com/tester/demo-layout/releases/download/"
            "v1.0.0/01.png"
        ]
        data["versions"][0]["downloadUrl"][0]["sizeBytes"] = 12185
        self.write(data)
        with contextlib.redirect_stdout(io.StringIO()):
            rc = validate_main([str(self.path), "--repo-root", str(self.root)])
        self.assertEqual(rc, 0)

    def test_warnings_only_exit_three(self):
        self.write(layout_data())
        with contextlib.redirect_stdout(io.StringIO()):
            rc = validate_main([str(self.path), "--repo-root", str(self.root)])
        self.assertEqual(rc, 3)

    def test_errors_exit_one(self):
        data = layout_data()
        del data["versions"][0]["downloadUrl"][0]["sha256"]
        self.write(data)
        with contextlib.redirect_stdout(io.StringIO()):
            rc = validate_main([str(self.path), "--repo-root", str(self.root)])
        self.assertEqual(rc, 1)

    def test_missing_file_exits_two(self):
        with contextlib.redirect_stderr(io.StringIO()):
            rc = validate_main(
                [
                    str(self.root / "src" / "layouts" / "nope.yaml"),
                    "--repo-root",
                    str(self.root),
                ]
            )
        self.assertEqual(rc, 2)

    def test_json_output(self):
        self.write(layout_data())
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = validate_main(
                [str(self.path), "--repo-root", str(self.root), "--json"]
            )
        self.assertEqual(rc, 3)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["type"], "layout")
        self.assertEqual(payload["id"], "demo_layout")
        self.assertEqual(payload["errors"], [])
        self.assertTrue(payload["warnings"])


if __name__ == "__main__":
    unittest.main()
