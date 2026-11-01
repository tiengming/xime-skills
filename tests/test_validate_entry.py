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

from tests.helpers import HTTPFixture, SKILL_ROOT, closed_port_url

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


PLUGIN_V2_ID = "com.example.demo_plugin"
PLUGIN_V1_ID = "com.example.legacy_plugin"
PLUGIN_V2_YAML = FIXTURES / "plugin-v2" / "valid.yaml"
PLUGIN_V2_MANIFEST = FIXTURES / "plugin-v2" / "manifest.json"
PLUGIN_V1_YAML = FIXTURES / "plugin-v1" / "valid.yaml"


def plugin_v2_data():
    return yaml.safe_load(PLUGIN_V2_YAML.read_text(encoding="utf-8"))


def plugin_v1_data():
    return yaml.safe_load(PLUGIN_V1_YAML.read_text(encoding="utf-8"))


def plugin_v2_manifest():
    return json.loads(PLUGIN_V2_MANIFEST.read_text(encoding="utf-8"))


class PluginValidationTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "src" / "plugins" / "v2").mkdir(parents=True)
        (self.root / "src" / "plugins" / "v1").mkdir(parents=True)

    def write(self, data, rel, filename):
        path = self.root / rel / filename
        path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
        return path

    def run_v2(self, data=None, manifest=None, asset_file=None):
        data = data if data is not None else plugin_v2_data()
        path = self.write(data, "src/plugins/v2", f"{data['id']}.yaml")
        manifest_path = None
        if manifest is not False:
            manifest = manifest if manifest is not None else plugin_v2_manifest()
            manifest_path = self.root / "manifest.json"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
            )
        return validate(
            path,
            repo_root=self.root,
            asset_file=asset_file,
            manifest_path=manifest_path,
        )

    def make_xipk(self, entries):
        path = self.root / "demo.xipk"
        with zipfile.ZipFile(path, "w") as zf:
            for name, payload in entries:
                zf.writestr(name, payload)
        return path

    def test_valid_v2_with_matching_manifest(self):
        report = self.run_v2()
        self.assertEqual(report.errors, [])
        self.assertEqual(report.type, "plugin-v2")
        self.assertTrue(any("activation" in w for w in report.warnings))

    def test_manifest_type_mismatch(self):
        manifest = plugin_v2_manifest()
        manifest["type"] = "emoji"
        report = self.run_v2(manifest=manifest)
        self.assertTrue(any("pluginType" in e for e in report.errors))

    def test_manifest_version_mismatch(self):
        manifest = plugin_v2_manifest()
        manifest["version"] = "0.2.0"
        report = self.run_v2(manifest=manifest)
        self.assertTrue(any("currentVersion" in e or "version" in e for e in report.errors))

    def test_manifest_platforms_mismatch(self):
        manifest = plugin_v2_manifest()
        manifest["platforms"] = ["ios"]
        report = self.run_v2(manifest=manifest)
        self.assertTrue(any("platforms" in e for e in report.errors))

    def test_manifest_icon_mismatch(self):
        manifest = plugin_v2_manifest()
        manifest["icon"] = "other.png"
        report = self.run_v2(manifest=manifest)
        self.assertTrue(any("icon" in e for e in report.errors))

    def test_missing_plugin_type(self):
        data = plugin_v2_data()
        del data["pluginType"]
        report = self.run_v2(data)
        self.assertTrue(any("pluginType" in e for e in report.errors))

    def test_unknown_plugin_type(self):
        data = plugin_v2_data()
        data["pluginType"] = "weird"
        report = self.run_v2(data)
        self.assertTrue(any("pluginType" in e for e in report.errors))

    def test_bad_activation(self):
        data = plugin_v2_data()
        data["activation"] = "always"
        report = self.run_v2(data)
        self.assertTrue(any("activation" in e for e in report.errors))

    def test_empty_platforms(self):
        data = plugin_v2_data()
        data["platforms"] = []
        report = self.run_v2(data)
        self.assertTrue(any("platforms" in e for e in report.errors))

    def test_xipk_without_main_js(self):
        asset = self.make_xipk([("manifest.json", "{}")])
        report = self.run_v2(asset_file=asset)
        self.assertTrue(any("main.js" in e for e in report.errors))

    def test_xipk_with_traversal(self):
        asset = self.make_xipk(
            [
                ("manifest.json", "{}"),
                ("main.js", "var plugin = {};"),
                ("../evil.txt", "x"),
            ]
        )
        report = self.run_v2(asset_file=asset)
        self.assertTrue(any(".." in e for e in report.errors))

    def test_valid_xipk_structure(self):
        asset = self.make_xipk(
            [
                ("manifest.json", "{}"),
                ("main.js", "var plugin = {};"),
                ("resources/icon.png", b"png"),
            ]
        )
        report = self.run_v2(asset_file=asset)
        self.assertEqual(report.errors, [])

    def test_v1_entry_warns_legacy(self):
        data = plugin_v1_data()
        path = self.write(data, "src/plugins/v1", f"{data['id']}.yaml")
        report = validate(path, repo_root=self.root)
        self.assertEqual(report.errors, [])
        self.assertTrue(
            any(
                "legacy plugin index; new plugins should use v2" in w
                for w in report.warnings
            )
        )

    def test_cli_manifest_mismatch_exits_one(self):
        data = plugin_v2_data()
        path = self.write(data, "src/plugins/v2", f"{data['id']}.yaml")
        manifest = plugin_v2_manifest()
        manifest["type"] = "emoji"
        manifest_path = self.root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            rc = validate_main(
                [
                    str(path),
                    "--repo-root",
                    str(self.root),
                    "--manifest",
                    str(manifest_path),
                ]
            )
        self.assertEqual(rc, 1)


RIME_YAML = FIXTURES / "rime" / "valid.yaml"
RIME_SCHEMA = FIXTURES / "rime" / "demo.schema.yaml"
MODEL_FILES_YAML = FIXTURES / "model" / "files-valid.yaml"
MODEL_ARCHIVE_YAML = FIXTURES / "model" / "archive-valid.yaml"


def rime_data():
    return yaml.safe_load(RIME_YAML.read_text(encoding="utf-8"))


def rime_schema():
    return yaml.safe_load(RIME_SCHEMA.read_text(encoding="utf-8"))


def model_files_data():
    return yaml.safe_load(MODEL_FILES_YAML.read_text(encoding="utf-8"))


def model_archive_data():
    return yaml.safe_load(MODEL_ARCHIVE_YAML.read_text(encoding="utf-8"))


class RimeValidationTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "src" / "rimes").mkdir(parents=True)

    def write(self, data):
        path = self.root / "src" / "rimes" / f"{data['id']}.yaml"
        path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
        return path

    def run_validate(self, data=None, schema=None):
        data = data if data is not None else rime_data()
        path = self.write(data)
        schema_path = None
        if schema is not None:
            schema_path = self.root / "demo.schema.yaml"
            schema_path.write_text(
                yaml.safe_dump(schema, allow_unicode=True), encoding="utf-8"
            )
        return validate(path, repo_root=self.root, schema_path=schema_path)

    def test_valid_rime_entry(self):
        report = self.run_validate()
        self.assertEqual(report.type, "rime")
        self.assertEqual(report.errors, [])

    def test_schema_id_mismatch(self):
        data = rime_data()
        data["id"] = "other_schema"
        report = self.run_validate(data, schema=rime_schema())
        self.assertTrue(any("schema_id" in e for e in report.errors))

    def test_schema_without_schema_id(self):
        data = rime_data()
        schema = rime_schema()
        del schema["schema_id"]
        report = self.run_validate(data, schema=schema)
        self.assertTrue(any("schema_id" in e for e in report.errors))

    def test_check_urls_network_failure_suggests_proxy(self):
        data = rime_data()
        data["versions"][0]["downloadUrl"][0]["url"] = closed_port_url()
        path = self.write(data)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            report = validate(path, repo_root=self.root, check_urls=True)
        self.assertTrue(any("网络错误" in w for w in report.warnings))
        self.assertIn("代理", err.getvalue())

    def test_dependencies_must_be_list(self):
        data = rime_data()

        data["dependencies"] = "demo_dep"
        report = self.run_validate(data)
        self.assertTrue(any("dependencies" in e for e in report.errors))

    def test_mutable_branch_version_warns(self):
        data = rime_data()
        data["currentVersion"] = "main"
        data["versions"][0]["version"] = "main"
        report = self.run_validate(data)
        self.assertTrue(
            any("mutable branch version" in w for w in report.warnings)
        )

    def test_gram_download_without_sha256_is_allowed(self):
        data = rime_data()
        data["versions"][0]["downloadUrl"].append(
            {
                "url": "https://github.com/tester/demo-schema/releases/"
                "download/v1.0.0/model.gram",
                "sha256": "",
                "size": "380 MB",
                "sizeBytes": 398458880,
            }
        )
        report = self.run_validate(data)
        self.assertEqual(report.errors, [])
        self.assertTrue(any(".gram" in w for w in report.warnings))

    def test_cli_schema_mismatch_exits_one(self):
        data = rime_data()
        data["id"] = "other_schema"
        path = self.write(data)
        schema_path = self.root / "demo.schema.yaml"
        schema_path.write_text(
            yaml.safe_dump(rime_schema(), allow_unicode=True), encoding="utf-8"
        )
        with contextlib.redirect_stdout(io.StringIO()):
            rc = validate_main(
                [
                    str(path),
                    "--repo-root",
                    str(self.root),
                    "--schema",
                    str(schema_path),
                ]
            )
        self.assertEqual(rc, 1)


class ModelValidationTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "src" / "models").mkdir(parents=True)

    def run_validate(self, data):
        path = self.root / "src" / "models" / f"{data['id']}.yaml"
        path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
        return validate(path, repo_root=self.root)

    def test_file_list_model(self):
        report = self.run_validate(model_files_data())
        self.assertEqual(report.errors, [])
        self.assertFalse(any("sizeBytes" in w for w in report.warnings))

    def test_archive_model(self):
        report = self.run_validate(model_archive_data())
        self.assertEqual(report.errors, [])

    def test_unknown_category(self):
        data = model_files_data()
        data["category"] = "nope"
        report = self.run_validate(data)
        self.assertTrue(any("category" in e for e in report.errors))

    def test_handwriting_category_warns(self):
        data = model_files_data()
        data["category"] = "handwriting"
        report = self.run_validate(data)
        self.assertEqual(report.errors, [])
        self.assertTrue(any("handwriting" in w for w in report.warnings))

    def test_needs_archive_or_files(self):
        data = model_files_data()
        del data["versions"][0]["files"]
        report = self.run_validate(data)
        self.assertTrue(
            any("archive" in e or "files" in e for e in report.errors)
        )

    def test_gram_file_skips_sha256_with_warning(self):
        data = model_files_data()
        data["versions"][0]["files"][0]["url"] = (
            "https://github.com/tester/demo-model/releases/download/v1.0.0/model.gram"
        )
        data["versions"][0]["files"][0]["sha256"] = ""
        report = self.run_validate(data)
        self.assertEqual(report.errors, [])
        self.assertTrue(any(".gram" in w for w in report.warnings))

    def test_size_mismatch_warns(self):
        data = model_files_data()
        data["size"] = "2.00 MB"
        report = self.run_validate(data)
        self.assertTrue(any("sizeBytes" in w for w in report.warnings))

    def test_missing_file_sha256_is_error(self):
        data = model_files_data()
        del data["versions"][0]["files"][0]["sha256"]
        report = self.run_validate(data)
        self.assertTrue(any("sha256" in e for e in report.errors))


if __name__ == "__main__":
    unittest.main()
