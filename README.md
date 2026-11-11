# Instana configuration.yaml Builder

Lokale Weboberfläche zum Einlesen, Bearbeiten und Speichern der Instana-Agent-Konfiguration
(`configuration.yaml`). Die Sensor-Optionen kommen aus einem erweiterbaren JSON-Katalog,
die Oberfläche läuft im Browser, der Server ist reines Python ohne Pflicht-Abhängigkeiten.

## Schnellstart

```bash
python3 instana_config_builder.py
```

Der Browser öffnet `http://127.0.0.1:8765/`. Weitere Aufrufe:

```bash
# bestehende Datei direkt laden
python3 instana_config_builder.py --input /opt/instana/agent/etc/instana/configuration.yaml

# anderen Port, keinen Browser öffnen
python3 instana_config_builder.py --port 0 --no-browser

# eigenen Katalog verwenden (z. B. Kundenvariante)
python3 instana_config_builder.py --catalog ./mein-katalog

# Konfigurations-Repository an anderem Ort (Standard: ./repository)
python3 instana_config_builder.py --repo ~/instana-configs
```

Voraussetzung: Python 3.7 oder neuer. Ist [PyYAML](https://pypi.org/project/PyYAML/) installiert,
wird es zum Lesen verwendet, sonst ein eingebauter YAML-Leser (deckt übliche Agent-Konfigurationen
ab; Anker, Aliase und Tags werden nicht unterstützt).

## Funktionen

- **Öffnen:** Dateibrowser auf dem lokalen Rechner, Upload oder Drag & Drop. Die enthaltenen
  Plugins erscheinen als Formulare; unbekannte Optionen bleiben als „zusätzliches YAML“ erhalten.
- **Speichern / Speichern unter:** Verzeichnis und Dateinamen frei wählbar, Rückfrage vor dem
  Überschreiben, automatische `.bak`-Sicherung mit Zeitstempel.
- **Ins Repository:** legt die Datei in einem lokalen Konfigurations-Repository ab. Verzeichnis und
  Dateiname ergeben sich aus den Tags (siehe unten).
- **Formulare** für rund 60 Sensoren mit dokumentierten Optionen, Standardwerten und Doku-Link;
  weitere rund 90 Plugin-Schlüssel mit freiem YAML. Eigene Schlüssel lassen sich hinzufügen.
- **Live-Vorschau** der YAML, optional mit Beschreibungen als Kommentar, Syntaxprüfung inklusive
  doppelter Schlüssel, Kopieren und Herunterladen.

Der Server lauscht nur auf `127.0.0.1` und lehnt Schreibzugriffe fremder Webseiten ab.

## Konfigurations-Repository (Vorbereitung auf Fleet Management)

Mit Instana Agent Fleet Management (derzeit Preview) werden Konfigurationsdateien mit
`instana-fleet import-config --include <datei>` hochgeladen und mit
`instana-fleet update-config --tag team=Organisation …` an alle Agenten mit diesem Tag verteilt. Das
Repository legt die Dateien so ab, dass der Pfad zum Selektor passt:

```
repository/
  .icb-repo.json                      gespeichertes Muster
  team=Organisation/
    env=production/
      configuration-shop.yaml         Tags: team=Organisation, env=production, shop
      configuration-availability-zone.yaml   Name „availability-zone“ im Dialog
```

Der Pfad wird aus einem Muster gebildet (Standard `team={tag:team}/env={tag:env}/configuration-{name}.yaml`):

| Platzhalter | Wert |
|---|---|
| `{tag:KEY}` | Wert des Tags `KEY=wert` (oder `KEY:wert`) aus `com.instana.plugin.host` → `tags` |
| `{zone}` | `availability-zone` aus `com.instana.plugin.generic.hardware` |
| `{tags}` | alle übrigen Tags, mit „-“ verbunden (bei `KEY=wert` nur der Wert) |
| `{name}` | Name aus dem Feld im Dialog, z. B. `availability-zone` → `configuration-availability-zone.yaml`; leer: wie `{tags}` |

Fehlt ein Wert, entfällt die Verzeichnisebene. Auf dem Agenten erlaubt sind nur
`configuration.yaml` und `configuration-<suffix>.yaml`; bei anderen Namen warnt der Dialog. Das
Muster lässt sich im Dialog ändern und wird beim Speichern in `.icb-repo.json` abgelegt.

Die Dateien gehören nicht ins Git: `repository/` und alle `configuration*.yaml` stehen in `.gitignore`.

## Projektstruktur

```
instana_config_builder.py   Startskript
icb/                        Python-Paket
  catalog.py                Katalog laden, Fragmente auflösen, prüfen
  importer.py               YAML ↔ Formularwerte
  yamlio.py, miniyaml.py    YAML lesen/schreiben (PyYAML oder eingebaut)
  files.py                  Öffnen, Verzeichnisliste, Speichern
  repo.py                   Konfigurations-Repository: Pfad aus Tags
  server.py                 HTTP-Server und Kommandozeile
web/                        Oberfläche (index.html, app.js, app.css)
catalog/                    Plugin-Katalog (eine JSON-Datei pro Plugin)
  plugins/<schlüssel>.json
  fragments/<name>.json     wiederverwendbare Feldgruppen
  categories.json           Reihenfolge der Gruppen
  schema.json               JSON-Schema für Editor-Unterstützung
tools/validate_catalog.py   Katalogprüfung (auch in der CI)
tests/                      unittest-Tests mit Beispieldateien
```

## Katalog erweitern

Jedes Plugin ist eine eigene Datei unter `catalog/plugins/`. Das Format ist in
[`catalog/README.md`](catalog/README.md) beschrieben. Nach jeder Änderung:

```bash
python3 tools/validate_catalog.py
python3 -m unittest discover -s tests -t .
```

VS Code prüft die Katalogdateien beim Bearbeiten automatisch gegen `catalog/schema.json`.

## Mitarbeit

Branching-Modell, Commit-Konventionen und Checkliste für Pull Requests stehen in
[`CONTRIBUTING.md`](CONTRIBUTING.md). Änderungen werden in [`CHANGELOG.md`](CHANGELOG.md) festgehalten.

## Hinweis zu den Quellen

Die Optionen stammen aus der IBM-Instana-Dokumentation bzw. der Beispielkonfiguration des Agents
(Stand November 2026). Instana-Sensoren ändern sich laufend; vor dem Rollout in Kundenumgebungen
bitte die verlinkte Doku gegenprüfen. Jede Plugin-Datei gibt ihre Quelle im Feld `source` an.
