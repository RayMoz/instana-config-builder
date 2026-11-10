# Changelog

Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), Versionen nach
[Semantic Versioning](https://semver.org/lang/de/).

## [Unreleased]

## [2.0.0] – 2026-11-10

### Geändert

- Projekt in Komponenten aufgeteilt: Python-Paket `icb/`, Oberfläche in `web/`,
  Katalog als eine JSON-Datei pro Plugin in `catalog/plugins/`.
- Katalogdateien mit sprechenden Attributnamen; wiederkehrende Feldgruppen als Fragmente
  (`db2-connection`, `java-sdk-target`, `dotnet-sdk-target`).
- Gruppenreihenfolge der Seitenleiste aus `catalog/categories.json`.

### Neu

- `--catalog` zum Laden eines anderen Katalogverzeichnisses.
- `tools/validate_catalog.py`, JSON-Schema `catalog/schema.json`, unittest-Suite,
  GitHub-Actions-CI (mit und ohne PyYAML), Beitragsrichtlinien.

## [1.2.1] – 2026-11-09

- Host: `configDisk` (`all`, `top20`, `false`).

## [1.2.0] – 2026-11-09

- Host: Linux-Optionen (`filesystems` als Liste oder include/exclude, `nfs_all`,
  `collectInstalledSoftware`, `combineTopProcesses`, `getFileInfo`, `collectPagingActivity`,
  `collectSystemProcess`, `collectRpcActivity`).

## [1.1.0] – 2026-11-09

- Öffnen per Dateibrowser, Upload und Drag & Drop; Speichern unter mit Überschreiben-Rückfrage.
- Eingebauter YAML-Leser, PyYAML optional.
- EUM-Autoinstrumentierung, HTTPd-Tracing, deklaratives Trace SDK für Java und .NET.

## [1.0.0] – 2026-11-09

- Erste Version: Web-UI, Katalog mit 148 Plugins, Live-Vorschau, Speichern mit Sicherung.
