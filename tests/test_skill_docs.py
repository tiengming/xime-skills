import json
import re
import unittest

import yaml

from tests.helpers import SKILL_ROOT


class SkillSkeletonTest(unittest.TestCase):
    def test_frontmatter_is_valid(self):
        text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        self.assertIsNotNone(m, "SKILL.md must start with YAML frontmatter")
        meta = {}
        for line in m.group(1).splitlines():
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
        self.assertEqual(meta["name"], "xime-index-submit")
        self.assertRegex(meta["name"], r"^[a-z0-9-]+$")
        self.assertTrue(meta["description"].startswith("Use when"))
        self.assertLessEqual(len(meta["description"]), 1024)


class TemplateTest(unittest.TestCase):
    TYPE_FIELDS = {
        "layout": "repo",
        "plugin-v2": "pluginType",
        "plugin-v1": "pluginType",
        "rime": "dependencies",
        "model": "category",
    }

    def test_templates_parse_and_have_required_fields(self):
        for name, type_field in self.TYPE_FIELDS.items():
            with self.subTest(template=name):
                path = SKILL_ROOT / "templates" / f"{name}.yaml"
                self.assertTrue(path.is_file(), f"missing template: {path}")
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
                self.assertIsInstance(data, dict)
                for key in (
                    "id",
                    "name",
                    "author",
                    "description",
                    "currentVersion",
                    "versions",
                ):
                    self.assertIn(key, data, f"{name}.yaml missing {key}")
                self.assertIn(type_field, data, f"{name}.yaml missing {type_field}")
                first = data["versions"][0]
                for key in ("version", "date", "changelog"):
                    self.assertIn(key, first, f"{name}.yaml versions[0] missing {key}")


class ReferenceDocsTest(unittest.TestCase):
    HEADINGS = {
        "index-rules.md": [
            "## 唯一事实来源",
            "## 五类条目",
            "## PR 只改 src",
            "## sha256 与 size",
            "## 版本更新",
            "## 常见 CI 检查",
        ],
        "layout.md": [
            "## 交付形态",
            "## zip 结构",
            "## xime.custom.yaml 约定",
            "## 截图规范",
            "## 更新版本",
            "## 常见错误",
        ],
        "plugin-v2.md": [
            "## 包结构",
            "## manifest 字段",
            "## 索引字段映射",
            "## xipm 命令",
            "## 版本与兼容",
            "## 常见错误",
        ],
        "plugin-v1.md": [
            "## 适用范围",
            "## 字段",
            "## 迁移到 v2",
        ],
        "rime.md": [
            "## 包结构",
            "## id 与 schema_id",
            "## 依赖",
            "## 版本与下载地址",
            "## 常见错误",
        ],
        "model.md": [
            "## 两种模型",
            "## category",
            "## files 与 archive",
            "## 大小计算",
            "## .gram 例外",
            "## 常见错误",
        ],
    }

    def read(self, name):
        path = SKILL_ROOT / "references" / name
        self.assertTrue(path.is_file(), f"missing reference: {path}")
        return path, path.read_text(encoding="utf-8")

    def test_required_headings(self):
        for name, headings in self.HEADINGS.items():
            with self.subTest(reference=name):
                _, text = self.read(name)
                for heading in headings:
                    self.assertRegex(
                        text,
                        rf"(?m)^{re.escape(heading)}$",
                        f"{name} missing heading {heading!r}",
                    )

    def test_relative_markdown_links_resolve(self):
        for name in self.HEADINGS:
            with self.subTest(reference=name):
                path, text = self.read(name)
                for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
                    target = target.strip()
                    if target.startswith(
                        ("http://", "https://", "mailto:", "#")
                    ):
                        continue
                    relative = target.split("#", 1)[0]
                    if not relative:
                        continue
                    resolved = (path.parent / relative).resolve()
                    self.assertTrue(
                        resolved.exists(),
                        f"{name}: broken relative link {target!r}",
                    )

    def test_index_rules_pins_upstream_commit(self):
        lock = json.loads(
            (
                SKILL_ROOT / "references" / "upstream.lock.json"
            ).read_text(encoding="utf-8")
        )
        _, text = self.read("index-rules.md")
        self.assertIn(lock["commit"], text)
