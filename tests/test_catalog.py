import json
import os
import unittest

from tests.helpers import ROOT  # noqa: F401  (setzt sys.path)
from icb.catalog import TYPES, default_dir, load_catalog, validate_catalog


class CatalogTest(unittest.TestCase):
    def test_catalog_is_valid(self):
        errors = validate_catalog()
        self.assertEqual(errors, [], "\n".join(errors))

    def test_filenames_match_keys(self):
        pdir = os.path.join(default_dir(), "plugins")
        for name in os.listdir(pdir):
            with open(os.path.join(pdir, name), encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["key"] + ".json", name)

    def test_fragments_are_resolved(self):
        plugins, _, _ = load_catalog()
        by = {p["key"]: p for p in plugins}

        def walk(fields):
            for f in fields:
                self.assertIn(f["t"], TYPES.values())
                self.assertNotIn("$ref", f)
                walk(f.get("f", []))

        for p in plugins:
            walk(p["fields"])
        db2_local = by["com.instana.plugin.db2"]["fields"][0]["f"]
        self.assertIn("customRunStatsPollRate", [f["k"] for f in db2_local])

    def test_invalid_catalog_is_reported(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "plugins"))
            bad = {
                "key": "com.instana.plugin.x",
                "name": "X",
                "category": "Agent",
                "fields": [
                    {"key": "a", "type": "nope"},
                    {"key": "a", "type": "enum"},
                    {"key": "b", "type": "object", "fields": [{"$ref": "fehlt"}]},
                ],
            }
            with open(os.path.join(d, "plugins", "falscher-name.json"), "w") as fh:
                json.dump(bad, fh)
            errors = "\n".join(validate_catalog(d))
            for part in (
                "unbekannter Typ",
                "doppelter Schlüssel",
                "enum braucht",
                "unbekanntes Fragment",
                "Dateiname",
            ):
                self.assertIn(part, errors)

    def test_files_match_json_schema(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema nicht installiert")
        import glob

        with open(os.path.join(default_dir(), "schema.json"), encoding="utf-8") as fh:
            validator = jsonschema.Draft7Validator(json.load(fh))
        for path in glob.glob(os.path.join(default_dir(), "plugins", "*.json")):
            with open(path, encoding="utf-8") as fh:
                errors = [e.message for e in validator.iter_errors(json.load(fh))]
            self.assertEqual(errors, [], path)


if __name__ == "__main__":
    unittest.main()
