import re
import unittest

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
