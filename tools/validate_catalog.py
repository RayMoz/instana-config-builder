#!/usr/bin/env python3
"""Prüft den Plugin-Katalog (Struktur, Typen, Fragmente, Dateinamen).

    python3 tools/validate_catalog.py            # Standardkatalog ./catalog
    python3 tools/validate_catalog.py --stats    # zusätzlich Übersicht
    python3 tools/validate_catalog.py pfad/zum/katalog

Exit-Code 0 = in Ordnung, 1 = Fehler gefunden. Wird auch in der CI ausgeführt.
"""

import argparse
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from icb.catalog import default_dir, load_catalog  # noqa: E402


def count_fields(fields):
    n = 0
    for f in fields:
        n += 1
        n += count_fields(f.get("f", []))
        for a in f.get("alts", []):
            n += count_fields(a.get("f", []))
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("catalog", nargs="?", default=default_dir())
    ap.add_argument("--stats", action="store_true", help="Übersicht je Kategorie ausgeben")
    args = ap.parse_args()
    plugins, categories, errors = load_catalog(args.catalog, strict=False)
    if errors:
        print("Katalog %s: %d Fehler" % (args.catalog, len(errors)))
        for e in errors:
            print("  - " + e)
        return 1
    with_opts = [p for p in plugins if p["fields"]]
    print(
        "Katalog in Ordnung: %d Plugins, %d mit Optionen, %d Felder insgesamt."
        % (len(plugins), len(with_opts), sum(count_fields(p["fields"]) for p in plugins))
    )
    if args.stats:
        by_cat = collections.Counter(p["cat"] for p in plugins)
        for c in categories:
            print("  %-30s %3d" % (c, by_cat.get(c, 0)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
