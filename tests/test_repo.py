import os
import tempfile
import unittest

import tests.helpers  # noqa: F401  (Pfad setzen)
from icb.repo import DEFAULT_PATTERN, Repo, extract, render


def info(tags, zone=""):
    return {"tags": tags, "zone": zone}


class RenderTest(unittest.TestCase):
    def test_default_pattern_uses_selectors_as_directories(self):
        rel, _, missing = render(None, info(["team=Organisation", "env=production", "shop", "app=web"]))
        self.assertEqual(rel, "team=Organisation/env=production/configuration-shop-web.yaml")
        self.assertEqual(missing, [])

    def test_missing_directory_level_is_dropped(self):
        rel, _, missing = render(DEFAULT_PATTERN, info(["env=test", "linux"]))
        self.assertEqual(rel, "env=test/configuration-linux.yaml")
        self.assertEqual(missing, ["tag:team"])

    def test_name_placeholder(self):
        tags = info(["team=Organisation", "env=production", "shop"])
        self.assertEqual(render(None, tags, "availability-zone")[0],
                         "team=Organisation/env=production/configuration-availability-zone.yaml")
        # leer → wie {tags}
        self.assertEqual(render(None, tags, "")[0], "team=Organisation/env=production/configuration-shop.yaml")
        # Drop-in ohne Tags
        self.assertEqual(render(None, info([]), "heartbeat")[0], "configuration-heartbeat.yaml")
        # unsichere Zeichen
        self.assertEqual(render(None, info([]), "../a b")[0], "configuration-a_b.yaml")

    def test_no_tags_gives_plain_name(self):
        self.assertEqual(render(DEFAULT_PATTERN, info([]))[0], "configuration.yaml")

    def test_colon_tags_zone_and_unsafe_chars(self):
        rel, _, _ = render("{zone}/configuration-{tag:app}.yaml", info(["app:Shop Web"], "Organisation"))
        self.assertEqual(rel, "Organisation/configuration-Shop_Web.yaml")

    def test_no_path_traversal(self):
        rel, _, _ = render("../{tags}/x", info(["../../etc"]))
        self.assertNotIn("..", rel.split("/"))
        with tempfile.TemporaryDirectory() as d:
            t = Repo(d).target("com.instana.plugin.host:\n  tags: ['../../etc']\n", "../../{tags}/configuration.yaml")
            self.assertTrue(t["path"].startswith(os.path.abspath(d)))

    def test_agent_file_name_warning(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(Repo(d).target("x: 1\n")["warnings"], [])
            self.assertTrue(Repo(d).target("x: 1\n", "agent-{tags}.yaml")["warnings"])

    def test_extract(self):
        e = extract("com.instana.plugin.host:\n  tags: ['a', 'env=prod']\n"
                    "com.instana.plugin.generic.hardware:\n  availability-zone: 'Zone 1'\n")
        self.assertEqual(e, {"tags": ["a", "env=prod"], "zone": "Zone 1"})


if __name__ == "__main__":
    unittest.main()
