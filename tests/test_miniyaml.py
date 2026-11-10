import glob
import os
import unittest

from tests.helpers import FIXTURES, HAVE_PYYAML, fixture
from icb.miniyaml import MiniYAMLError, mini_dump, mini_load


class MiniYamlTest(unittest.TestCase):
    def test_edge_cases(self):
        d = mini_load(fixture("edge-cases.yaml"))
        prom = d["com.instana.plugin.prometheus"]
        self.assertEqual(prom["customMetricSources"][0]["metricNameIncludeRegex"], "http_.*#kein-kommentar")
        self.assertEqual(prom["customMetricSources"][0]["labels"], {"app": "shop", "tier": "web"})
        self.assertEqual(
            d["com.instana.plugin.mysql"]["conditionOperator"], [">", ">=", "<", "<=", "=", "!="]
        )
        self.assertEqual(d["com.instana.plugin.mysql"]["password"], "it's secret")
        c = d["com.instana.plugin.custom"]
        self.assertEqual(c["script"], '#!/bin/sh\necho "hallo"\n')
        self.assertEqual(c["folded"], "eine lange Zeile")
        self.assertEqual(c["flags"], [True, False, True, False, None, 31, 1.5, -3])
        self.assertEqual(c["nested"], [["a", "b"], "c"])

    def test_duplicate_keys(self):
        text = "a:\n  b: 1\na:\n  b: 2\n"
        with self.assertRaises(MiniYAMLError):
            mini_load(text)
        warnings = []
        self.assertEqual(mini_load(text, allow_dup=True, warnings=warnings), {"a": {"b": 2}})
        self.assertEqual(len(warnings), 1)

    def test_errors_have_line_numbers(self):
        with self.assertRaisesRegex(MiniYAMLError, "Zeile 3"):
            mini_load("a:\n  b: 1\n    c: 2\n")

    def test_dump_roundtrip(self):
        for path in glob.glob(os.path.join(FIXTURES, "*.yaml")):
            with open(path, encoding="utf-8") as fh:
                data = mini_load(fh.read())
            self.assertEqual(mini_load(mini_dump(data)), data, path)

    @unittest.skipUnless(HAVE_PYYAML, "PyYAML nicht installiert")
    def test_same_result_as_pyyaml(self):
        import yaml

        loader = type("L", (yaml.SafeLoader,), {})
        loader.add_constructor("tag:yaml.org,2002:value", lambda ldr, node: ldr.construct_scalar(node))
        for path in glob.glob(os.path.join(FIXTURES, "*.yaml")):
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            self.assertEqual(mini_load(text), yaml.load(text, Loader=loader), path)
            self.assertEqual(yaml.load(mini_dump(mini_load(text)), Loader=loader), mini_load(text), path)


if __name__ == "__main__":
    unittest.main()
