import os
import tempfile
import unittest

import tests.helpers  # noqa: F401  (Pfad setzen)
from icb.merge import evaluate, merge_files, order_files

FILES = {
    "/r/team=a/configuration-bb.yaml": "com.instana.plugin.host:\n  poll_rate: 30\n  tags: ['c']\n",
    "/r/configuration-aa.yaml": "com.instana.plugin.host:\n  poll_rate: 10\n  tags: ['b', 'a']\n"
    "com.instana.tracing:\n  extra-http-headers: ['x-a']\n",
    "/r/x/configuration.yaml": "com.instana.plugin.host:\n  poll_rate: 1\n  tags: ['a']\n"
    "  filesystems:\n    include: ['/']\n",
    "/r/notes.yaml": "x: 1\n",
}


class MergeTest(unittest.TestCase):
    def run_merge(self, files=FILES):
        return merge_files(list(files), read=files.get)

    def test_order_configuration_yaml_first_then_alphanumeric(self):
        self.assertEqual(
            [os.path.basename(p) for p in order_files(FILES)],
            ["configuration.yaml", "configuration-aa.yaml", "configuration-bb.yaml", "notes.yaml"],
        )
        # Zeichencode: Großbuchstaben vor Kleinbuchstaben, Ziffern davor
        self.assertEqual(
            [os.path.basename(p) for p in order_files(["/configuration-b.yaml", "/configuration-B.yaml", "/configuration-1.yaml"])],
            ["configuration-1.yaml", "configuration-B.yaml", "configuration-b.yaml"],
        )

    def test_later_file_wins_lists_are_extended(self):
        r = self.run_merge()
        host = r["data"]["com.instana.plugin.host"]
        self.assertEqual(host["poll_rate"], 30)
        self.assertEqual(host["tags"], ["a", "b", "c"])
        self.assertEqual(host["filesystems"], {"include": ["/"]})
        self.assertEqual(r["data"]["com.instana.tracing"]["extra-http-headers"], ["x-a"])
        conf = {tuple(c["path"]): [s["file"] for s in c["steps"]] for c in r["conflicts"]}
        self.assertEqual(
            conf, {("com.instana.plugin.host", "poll_rate"): ["configuration.yaml", "configuration-aa.yaml", "configuration-bb.yaml"]}
        )

    def test_unknown_names_are_ignored(self):
        r = self.run_merge()
        notes = [e for e in r["order"] if e["name"] == "notes.yaml"][0]
        self.assertFalse(notes["used"])
        self.assertNotIn("x", r["data"])

    def test_same_file_name_twice_warns(self):
        files = {"/a/configuration-x.yaml": "k: 1\n", "/b/configuration-x.yaml": "k: 2\n"}
        r = self.run_merge(files)
        self.assertTrue(r["warnings"])
        self.assertEqual(r["data"]["k"], 2)

    def test_evaluate_annotated_output(self):
        r = evaluate(list(FILES), read=FILES.get)
        self.assertEqual(r["files"], 3)
        self.assertIn("poll_rate: 30  # configuration-bb.yaml  ⟵ überschreibt configuration.yaml: 1", r["annotated"])
        self.assertIn("# configuration.yaml + configuration-aa.yaml + configuration-bb.yaml", r["annotated"])
        self.assertNotIn("#", r["yaml"])

    def test_evaluate_reads_real_files(self):
        with tempfile.TemporaryDirectory() as d:
            for sub, name, text in [("a", "configuration.yaml", "k: 1\n"), ("b", "configuration-z.yaml", "k: 2\n")]:
                os.makedirs(os.path.join(d, sub))
                with open(os.path.join(d, sub, name), "w") as fh:
                    fh.write(text)
            r = evaluate([os.path.join(d, "b", "configuration-z.yaml"), os.path.join(d, "a", "configuration.yaml")])
            self.assertEqual(r["yaml"], "k: 2\n")


if __name__ == "__main__":
    unittest.main()
