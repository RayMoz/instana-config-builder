# Changelog

Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), Versionen nach
[Semantic Versioning](https://semver.org/lang/de/).

## [Unreleased]

### Neu

- Host: AIX-Optionen laut IBM-Doku „Monitoring an AIX host“ (`collectSystemId`, `useMpstat`,
  `collectPhysicalProcessorUtil`, `collectIndividualCpuMetrics`, `collectIOActivity`,
  `collectProcessStatistics`, `collectAllDisks`, `collectAllVolumeGroups`, `collectAllLogicalVolumes`,
  `collectAllAixFilesystems`, `collectNfsStatistics`, `collectRpcStatistics`, `aixEventsPollRate`).
- Katalog: Feld-Attribut `os` für betriebssystemspezifische Optionen; Linux-Optionen des Host-Plugins
  entsprechend gekennzeichnet.
- Oberfläche: Kennzeichen am Feld und Umschalter „Optionen für: Alle | Linux | AIX“ auf der Karte.
- Host: Windows-Optionen laut IBM-Doku „Monitoring a Windows host“ (`smb`, `winServiceRegex`,
  `wsfcEnabled`) sowie `poll_rate` für alle Betriebssysteme; Hinweis auf Laufwerksbuchstaben bei
  `filesystems`.
- Host: macOS, Solaris und IBM i laut den jeweiligen IBM-Doku-Seiten. Neue Schlüssel gibt es dort
  nicht; `collectSystemId` gilt jetzt auch für diese Systeme, `filesystems` nennt Solaris-Gerätenamen.
  Der Doku-Link der Karte zeigt auf die Übersicht „Monitoring host“.
- Oberfläche: Jede Plugin-Karte lässt sich einzeln ein- und ausklappen – per Pfeil-Schaltfläche oder
  Klick auf eine freie Stelle der Kopfzeile (auch per Tastatur). Eingeklappt bleiben nur
  Kopfzeile und Schaltflächen sichtbar, dazu die Anzahl gesetzter Werte. „Alle einklappen“ und
  „Alle ausklappen“ über dem Editor; der Zustand wird im Browser gespeichert.

### Behoben

- Doku-Links: IBM hat die Pfade `docs/en/SSE1JP5/…` und `docs/SSE1JP5/…` abgeschaltet (404).
  Alle Links zeigen jetzt auf `https://www.ibm.com/docs/SSE1JP5_current/…`; alle Zielseiten geprüft.
- Doku-Links: 62 Plugins, die bisher nur auf die allgemeine Übersicht „Configuring and monitoring
  supported technologies“ verwiesen, verlinken jetzt die passende Sensor-Seite (z. B. Tomcat, AWS S3,
  Google Cloud Run, PHP-FPM, Java-Profiling). Für `db2z` und `ibmapmproxy` gibt es derzeit keine
  eigene IBM-Seite; dort bleibt der Link auf die Übersicht.

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
