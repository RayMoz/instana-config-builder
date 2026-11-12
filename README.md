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
- **Fleet-Befehle:** zeigt die `instana-fleet`-Befehle zum Hochladen und Verteilen der gespeicherten
  Datei (siehe unten).
- **Endgültige Konfig prüfen:** mehrere `configuration*.yaml` aus beliebigen Verzeichnissen
  auswählen und so zusammenführen, wie der Agent sie auswertet (siehe unten).
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

### Fleet-Befehle

„Fleet-Befehle …“ erzeugt für die gespeicherte Datei die Befehle – angezeigt, nicht ausgeführt:

1. `instana-fleet import-config --type com.ibm.instana.agent --include <datei> --config-name … --config-version …`
2. `instana-fleet list-configs …` zum Nachschlagen der Configuration-ID
3. `instana-fleet update-config --type com.ibm.instana.agent --tag key=wert … --configuration-id …`

Vorgeschlagen werden der Konfigurationsname (aus Verzeichnissen und Dateiname, z. B.
`organisation-production-basis`), die Version (zuletzt verwendete je Datei, „+1“ erhöht die
Patch-Version) und als Selektoren alle `key=wert`-Verzeichnisse des Repository-Pfads; weitere Tags
(z. B. `hostname=…`) lassen sich ergänzen. Hinweise erscheinen u. a., wenn der Selektor eine
Verzeichnisebene weglässt (dann erreicht `update-config` auch Agenten außerhalb der Gruppe). Ob die
CLI mehrere `--tag` kombiniert, beschreibt die Preview-Doku nicht – das ist in einer Sandbox zu prüfen.
Die Befehle lassen sich kopieren oder als Shell-Skript herunterladen.

## Endgültige Konfiguration prüfen

Der Agent liest `configuration.yaml` und alle `configuration-<suffix>.yaml` aus `etc/instana/`. Die
Instana-Oberfläche zeigt alle Dateien, aber nicht, welcher Wert bei Dopplungen gilt. Der Dialog
„Endgültige Konfig prüfen …“ wertet die ausgewählten Dateien wie der Agent aus:

1. zuerst `configuration.yaml`, dann alle `configuration-*.yaml` streng alphanumerisch
   (Zeichencode: `configuration-aa.yaml` vor `configuration-bb.yaml`, Großbuchstaben vor Kleinbuchstaben)
2. Mappings werden zusammengeführt; bei gleichen Schlüsseln gewinnt die später gelesene Datei
3. Listen (z. B. `tags`) werden ergänzt, nicht ersetzt

Maßgeblich ist nur der Dateiname. Dateien mit anderen Namen werden angezeigt, aber nicht gelesen;
gleiche Dateinamen aus verschiedenen Verzeichnissen werden gemeldet, da es auf dem Agenten nur
eine Datei dieses Namens geben kann. Das Ergebnis zeigt die überschriebenen Optionen als Tabelle und
die endgültige YAML, wahlweise mit Herkunft je Wert als Kommentar. Es lässt sich kopieren oder in den
Editor übernehmen.

## Projektstruktur

```
instana_config_builder.py   Startskript
icb/                        Python-Paket
  catalog.py                Katalog laden, Fragmente auflösen, prüfen
  importer.py               YAML ↔ Formularwerte
  yamlio.py, miniyaml.py    YAML lesen/schreiben (PyYAML oder eingebaut)
  files.py                  Öffnen, Verzeichnisliste, Speichern
  repo.py                   Konfigurations-Repository: Pfad aus Tags
  merge.py                  mehrere Dateien wie der Agent zusammenführen
  fleet.py                  instana-fleet-Befehle erzeugen
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
