#!/usr/bin/env python3
"""
Instana configuration.yaml Builder
==================================

Lokale Weboberfläche zum Einlesen, Bearbeiten und Speichern einer
Instana-Agent-Konfiguration (configuration.yaml).

Start:
    python3 instana_config_builder.py
    python3 instana_config_builder.py --input /opt/instana/agent/etc/instana/configuration.yaml
    python3 instana_config_builder.py --catalog ./mein-katalog --port 0 --no-browser

Benötigt nur Python 3.7+. Ist PyYAML installiert, wird es zum Lesen verwendet,
sonst ein eingebauter YAML-Leser. Details siehe README.md.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from icb.server import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
