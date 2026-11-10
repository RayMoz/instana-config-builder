import unittest

from tests.helpers import fixture
from icb.catalog import load_catalog
from icb.importer import import_yaml, validate_yaml

PLUGINS, _, _ = load_catalog()
BY_KEY = {p["key"]: p for p in PLUGINS}


def section(result, key):
    return next(p for p in result["plugins"] if p["key"] == key)


class ImporterTest(unittest.TestCase):
    def test_sample(self):
        r = import_yaml(fixture("sample.yaml"), BY_KEY)
        mq = section(r, "com.instana.plugin.ibmmq")["values"]
        self.assertEqual(mq["poll_rate"], "60")
        self.assertEqual(mq["queueManagers"][0]["name"], "QM1")
        jt = section(r, "com.instana.plugin.javatrace")["values"]["instrumentation"]
        self.assertEqual(jt["plugins"], [["Redis", "false"]])
        mysql = section(r, "com.instana.plugin.mysql")
        self.assertIn("conditionOperator", mysql["extra"])
        foo = section(r, "com.instana.plugin.foo")
        self.assertTrue(foo["custom"])

    def test_host_filesystems_both_forms(self):
        a = section(import_yaml(fixture("host-list.yaml"), BY_KEY), "com.instana.plugin.host")["values"]
        self.assertEqual(a["filesystems"], ["/dev/sda1", "tmpfs:/sys/fs/cgroup"])
        b = section(import_yaml(fixture("host-include.yaml"), BY_KEY), "com.instana.plugin.host")["values"]
        self.assertEqual(
            b["filesystems"], {"include": ["/dev/xvdd", "tmpfs:/tmp"], "exclude": ["/dev/xvda2"]}
        )

    def test_host_aix_example(self):
        r = section(import_yaml(fixture("host-aix.yaml"), BY_KEY), "com.instana.plugin.host")
        self.assertEqual(r["extra"], "", "alle AIX-Optionen sollten im Katalog stehen")
        v = r["values"]
        self.assertEqual(v["aixEventsPollRate"], "900")
        self.assertEqual(v["collectIOActivity"], "false")
        self.assertEqual(v["filesystems"]["exclude"], ["/dev/hd10opt"])

    def test_host_windows_example(self):
        r = section(import_yaml(fixture("host-windows.yaml"), BY_KEY), "com.instana.plugin.host")
        self.assertEqual(r["extra"], "", "alle Windows-Optionen sollten im Katalog stehen")
        v = r["values"]
        self.assertEqual(v["poll_rate"], "5")
        self.assertEqual(v["smb"], ["\\\\server\\smbshare", "Y:"])
        self.assertEqual(v["winServiceRegex"], "(Sensor|Device)")
        self.assertEqual(v["wsfcEnabled"], "true")
        self.assertEqual(v["filesystems"]["include"], ["C", "D"])

    def test_host_os_tags(self):
        fields = {f["k"]: f for f in BY_KEY["com.instana.plugin.host"]["fields"]}
        self.assertEqual(fields["useMpstat"]["os"], ["aix"])
        self.assertEqual(fields["nfs_all"]["os"], ["linux"])
        self.assertEqual(fields["wsfcEnabled"]["os"], ["windows"])
        self.assertEqual(fields["collectSystemId"]["os"], ["aix", "macos", "solaris", "ibmi"])
        self.assertNotIn("os", fields["filesystems"])
        self.assertNotIn("os", fields["poll_rate"])

    def test_unknown_subkeys_fall_back_to_yaml(self):
        text = "com.instana.plugin.javatrace:\n  instrumentation:\n    enabled: true\n    neuesFeature: 1\n"
        v = section(import_yaml(text, BY_KEY), "com.instana.plugin.javatrace")["values"]
        self.assertIn("$raw", v["instrumentation"])
        self.assertIn("neuesFeature", v["instrumentation"]["$raw"])

    def test_duplicate_top_level_keys_warn(self):
        r = import_yaml(
            "com.instana.plugin.host:\n  tags: [a]\ncom.instana.plugin.host:\n  tags: [b]\n", BY_KEY
        )
        self.assertTrue(r["warnings"])
        self.assertEqual(section(r, "com.instana.plugin.host")["values"]["tags"], ["b"])

    def test_validate(self):
        self.assertTrue(validate_yaml(fixture("sample.yaml"), BY_KEY)["ok"])
        bad = validate_yaml("a:\n  b: 1\n   c: 2\n", BY_KEY)
        self.assertFalse(bad["ok"])


if __name__ == "__main__":
    unittest.main()
