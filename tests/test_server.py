import json
import os
import tempfile
import threading
import unittest
import urllib.request

from tests.helpers import fixture
from icb.server import make_server


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo_dir = tempfile.TemporaryDirectory()
        cls.httpd = make_server(port=0, repo=cls.repo_dir.name)
        cls.base = "http://127.0.0.1:%d" % cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.repo_dir.cleanup()

    def get(self, path):
        with urllib.request.urlopen(self.base + path) as r:
            return r.read().decode("utf-8")

    def post(self, path, body, origin=None):
        req = urllib.request.Request(
            self.base + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
        )
        if origin:
            req.add_header("Origin", origin)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_static_and_catalog(self):
        self.assertIn("<title>", self.get("/"))
        self.assertIn("function", self.get("/app.js"))
        cat = json.loads(self.get("/api/catalog"))
        self.assertGreater(len(cat["plugins"]), 100)
        self.assertIn("Agent", cat["categories"])

    def test_import(self):
        status, r = self.post("/api/import", {"yaml": fixture("sample.yaml")})
        self.assertEqual(status, 200)
        self.assertTrue(r["ok"])

    def test_save_open_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "unter", "test.yaml")
            _, r = self.post("/api/save", {"path": path, "yaml": "com.instana.plugin.host:\n  tags: [a]\n"})
            self.assertTrue(r["ok"], r)
            _, r = self.post("/api/save", {"path": path, "yaml": "x: 1\n"})
            self.assertTrue(r.get("exists"))
            _, r = self.post("/api/save", {"path": path, "yaml": "x: 1\n", "overwrite": True})
            self.assertTrue(r["ok"])
            self.assertEqual(len([n for n in os.listdir(os.path.dirname(path)) if ".bak-" in n]), 1)
            _, r = self.post("/api/open", {"path": path})
            self.assertEqual(r["plugins"][0]["key"], "x")
            ls = json.loads(self.get("/api/ls?dir=" + urllib.request.quote(os.path.dirname(path))))
            self.assertEqual([e["name"] for e in ls["entries"]], ["test.yaml"])

    def test_repo_target_and_save(self):
        text = "com.instana.plugin.host:\n  tags:\n    - 'team=Organisation'\n    - 'env=production'\n    - 'shop'\n"
        info = json.loads(self.get("/api/info"))["repo"]
        self.assertEqual(os.path.realpath(info["dir"]), os.path.realpath(self.repo_dir.name))
        _, t = self.post("/api/repo/target", {"yaml": text})
        self.assertEqual(t["rel"], "team=Organisation/env=production/configuration-shop.yaml")
        self.assertFalse(t["exists"])
        _, r = self.post("/api/repo/save", {"yaml": text})
        self.assertTrue(r["ok"], r)
        self.assertTrue(os.path.isfile(os.path.join(self.repo_dir.name, "team=Organisation", "env=production",
                                                    "configuration-shop.yaml")))
        _, r = self.post("/api/repo/save", {"yaml": text})
        self.assertTrue(r.get("exists"))
        _, t = self.post("/api/repo/target", {"yaml": text, "name": "availability-zone"})
        self.assertEqual(t["rel"], "team=Organisation/env=production/configuration-availability-zone.yaml")
        # eigenes Muster wird im Repository gespeichert
        _, r = self.post("/api/repo/save", {"yaml": text, "pattern": "{tag:env}/configuration-{tags}.yaml"})
        self.assertEqual(r["rel"], "production/configuration-Organisation-shop.yaml")
        self.assertEqual(json.loads(self.get("/api/info"))["repo"]["pattern"], "{tag:env}/configuration-{tags}.yaml")

    def test_foreign_origin_rejected(self):
        status, _ = self.post("/api/save", {"path": "/tmp/x.yaml", "yaml": ""}, origin="http://evil.example")
        self.assertEqual(status, 403)


if __name__ == "__main__":
    unittest.main()
