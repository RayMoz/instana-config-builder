# Plugin-Katalog

Jede Datei unter `plugins/` beschreibt **einen** Schlüssel der obersten Ebene der
`configuration.yaml`. Der Dateiname ist der Schlüssel plus `.json`.

```json
{
  "key": "com.instana.plugin.redis",
  "name": "Redis",
  "category": "Datenbanken",
  "docs": "https://www.ibm.com/docs/en/SSE1JP5/src/pages/ecosystem/redis/index.html",
  "source": "ibm-docs",
  "note": "optionaler Hinweis oben auf der Karte",
  "fields": [
    { "key": "password", "type": "secret", "description": "Passwort" },
    { "key": "poll_rate", "type": "integer", "default": 1, "unit": "s", "description": "Abfrageintervall" }
  ]
}
```

## Plugin-Attribute

| Attribut   | Pflicht | Bedeutung                                                              |
| ---------- | ------- | ---------------------------------------------------------------------- |
| `key`      | ja      | Schlüssel in der YAML, gleich dem Dateinamen                           |
| `name`     | ja      | Anzeigename                                                            |
| `category` | ja      | Gruppe in der Seitenleiste, muss in `categories.json` stehen           |
| `fields`   | ja      | Felder (leer = nur freies YAML)                                        |
| `docs`     |         | Link zur Doku                                                          |
| `source`   |         | `ibm-docs`, `agent-template` (Beispielkonfiguration), `free`, `user`   |
| `note`     |         | Hinweistext auf der Karte                                              |

## Feldtypen

| `type`         | Eingabe                        | YAML-Ausgabe                                   |
| -------------- | ------------------------------ | ---------------------------------------------- |
| `string`       | Textfeld                       | `key: 'wert'`                                  |
| `secret`       | Passwortfeld                   | `key: 'wert'`                                  |
| `integer`      | Zahlenfeld                     | `key: 10`                                      |
| `boolean`      | – / true / false               | `key: true`                                    |
| `enum`         | Auswahl aus `options`          | `key: 'wert'` (mit `unquoted: true` ohne '…')  |
| `stringList`   | ein Eintrag pro Zeile          | Liste                                          |
| `keyValue`     | Schlüssel/Wert-Zeilen          | Mapping; `valueType: boolean` für true/false   |
| `object`       | verschachtelte `fields`        | Mapping                                        |
| `objectList`   | Einträge mit `fields`          | Liste von Mappings                             |
| `namedObjects` | Einträge mit Namen + `fields`  | Mapping Name → Mapping (z. B. Queue Manager)   |
| `yaml`         | freier YAML-Text               | eingerückt übernommen                          |
| `oneOf`        | Umschalter zwischen Formen     | `alternatives`: `stringList` oder `object`     |

## Feld-Attribute

`key`, `type`, `description` (deutsch, kurz), `default` (nur Anzeige), `unit`, `placeholder`,
`options` (enum), `suggestions` (Vorschläge bei string), `example` (Beispielwerte zum Einsetzen),
`unquoted`, `keyLabel`/`keyPlaceholder` (namedObjects/keyValue), `valueType` (keyValue),
`label` (oneOf-Alternative), `fields`, `alternatives`.

## Fragmente

Wiederkehrende Feldgruppen liegen in `fragments/<name>.json` (`{"description": …, "fields": [...]}`)
und werden mit `{"$ref": "<name>"}` eingebunden – entweder als Listeneintrag (Felder werden an
dieser Stelle eingefügt) oder als kompletter Wert von `fields`.

## Prüfen

```bash
python3 tools/validate_catalog.py --stats
```

Geprüft werden u. a. Typen, Pflichtattribute, doppelte Schlüssel, unbekannte Attribute
(Tippfehler), Fragment-Verweise, Kategorien und Dateinamen.
