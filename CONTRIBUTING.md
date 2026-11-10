# Mitarbeit

## Branching-Modell

- **`main`** ist immer lauffähig und wird nur per Pull Request geändert
  (auf GitHub als geschützter Branch einrichten: *Settings → Branches → Branch protection rule*,
  „Require a pull request“ und „Require status checks: CI“).
- Arbeit findet auf kurzlebigen Branches statt, die von `main` abzweigen:

| Präfix       | Zweck                                       | Beispiel                       |
| ------------ | ------------------------------------------- | ------------------------------ |
| `catalog/`   | neue oder geänderte Optionen im Katalog     | `catalog/host-aix`             |
| `feature/`   | neue Funktionen in Server oder Oberfläche   | `feature/diff-ansicht`         |
| `fix/`       | Fehlerbehebungen                            | `fix/import-flow-mapping`      |
| `docs/`      | nur Dokumentation                           | `docs/katalog-format`          |

- Pro Branch ein Thema. Katalogänderungen möglichst je Plugin bzw. Sensorbereich bündeln –
  da jedes Plugin eine eigene Datei hat, gibt es so kaum Merge-Konflikte.
- Merge per *Squash and merge* oder *Rebase and merge*, danach Branch löschen.

```bash
git switch main && git pull
git switch -c catalog/host-aix
# … ändern, prüfen, committen …
git push -u origin catalog/host-aix
# Pull Request auf GitHub öffnen
```

## Commits

Kurze Betreffzeile im Imperativ, optional mit Bereich:

```
katalog(host): AIX-Optionen ergänzen
ui: Betriebssystem-Filter für Host-Optionen
fix(import): Flow-Mappings mit Anführungszeichen
```

## Vor dem Pull Request

```bash
python3 tools/validate_catalog.py
python3 -m unittest discover -s tests -t .
```

Optional (läuft auch in der CI): `ruff check .`, `black --check .`,
`npx prettier@3.3.3 --check "web/**/*.{js,css,html}" "catalog/**/*.json"`.

Neue Optionen bitte einmal in der Oberfläche ausprobieren (Formular ausfüllen → YAML prüfen →
speichern → wieder öffnen) und im `CHANGELOG.md` unter „Unreleased“ eintragen.

## Releases

Versionsnummer in `icb/__init__.py` anheben, `CHANGELOG.md` ergänzen und auf `main` ein Tag setzen:

```bash
git tag -a v2.1.0 -m "v2.1.0" && git push origin v2.1.0
```
