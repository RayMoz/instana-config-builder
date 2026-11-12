import os
import tempfile
import unittest

import tests.helpers  # noqa: F401  (Pfad setzen)
from icb.fleet import commands, plan, sh, suggest


class FleetTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        d = os.path.join(self.root, "team=Organisation", "env=production")
        os.makedirs(d)
        self.path = os.path.join(d, "configuration-basis.yaml")
        with open(self.path, "w") as fh:
            fh.write("com.instana.plugin.host:\n  tags: ['team=Organisation', 'env=production', 'app:shop']\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_suggest_from_repository_path_and_tags(self):
        s = suggest(self.path, self.root, open(self.path).read())
        self.assertEqual(s["dirSelectors"], ["team=Organisation", "env=production"])
        self.assertEqual(s["selectors"], ["team=Organisation", "env=production", "app=shop"])
        self.assertEqual(s["configName"], "organisation-production-basis")

    def test_suggest_outside_repository(self):
        s = suggest("/x/configuration.yaml", self.root, "com.instana.plugin.host:\n  tags: ['env=test']\n")
        self.assertEqual(s, {"configName": "basis", "selectors": ["env=test"], "dirSelectors": [], "inRepo": False})

    def test_plan_defaults_to_all_directory_selectors(self):
        r = plan({"path": self.path}, self.root)
        self.assertEqual(r["tags"], ["team=Organisation", "env=production"])
        self.assertIn("--include %s" % self.path, r["script"])
        self.assertIn("--config-name organisation-production-basis", r["script"])
        self.assertIn("--config-version 1.0.0", r["script"])
        self.assertIn("--tag team=Organisation \\\n  --tag env=production", r["script"])
        self.assertTrue(any("Mehrere --tag" in w for w in r["warnings"]))

    def test_partial_selector_warns(self):
        r = plan({"path": self.path, "tags": ["env=production"]}, self.root)
        self.assertTrue(any("lässt team=Organisation weg" in w for w in r["warnings"]))

    def test_validation(self):
        r = commands("/nope/agent.yaml", "", "1.0", ["kein-selektor"])
        w = " ".join(r["warnings"])
        for part in ("configuration-<suffix>.yaml", "existiert nicht", "Konfigurationsnamen", "1.0.0", "key=wert"):
            self.assertIn(part, w)

    def test_server_and_quoting(self):
        r = commands(self.path, "a b", "1.2.3", ["team=O'Neil"], server="https://instana.example.com/")
        self.assertIn("--server instana.example.com", r["script"])
        self.assertIn("--config-name 'a b'", r["script"])
        self.assertIn("--tag 'team=O'\\''Neil'", r["script"])
        self.assertEqual(sh("a b'c"), "'a b'\\''c'")


if __name__ == "__main__":
    unittest.main()
