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
