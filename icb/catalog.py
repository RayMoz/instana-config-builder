"""Plugin-Katalog: JSON-Dateien laden, Fragmente auflösen, prüfen.

Aufbau des Katalogverzeichnisses (siehe catalog/README.md):

    catalog/
      categories.json        Reihenfolge der Gruppen
      fragments/<name>.json  wiederverwendbare Feldlisten ({"$ref": "<name>"})
      plugins/<key>.json     ein Plugin je Datei, Dateiname = Schlüssel

Die Dateien verwenden sprechende Attributnamen (key, type, description …).
Für die Oberfläche werden sie in eine kompakte interne Form übersetzt
(k, t, d …), damit die Web-UI klein bleibt.
"""

import copy
import json
import os

TYPES = {
    "string": "str",
    "secret": "secret",
    "integer": "int",
    "boolean": "bool",
    "enum": "enum",
    "stringList": "list",
    "keyValue": "kv",
    "object": "obj",
    "objectList": "objlist",
    "namedObjects": "map",
    "yaml": "yaml",
    "oneOf": "alt",
}
FIELD_ATTRS = {
    "key": "k",
    "type": "t",
    "description": "d",
    "default": "def",
    "unit": "u",
    "placeholder": "ph",
    "options": "opts",
    "fields": "f",
    "example": "ex",
    "keyLabel": "kl",
    "keyPlaceholder": "kph",
    "valueType": "vt",
    "suggestions": "sug",
    "unquoted": "bare",
    "alternatives": "alts",
    "label": "label",
    "os": "os",
}
PLUGIN_ATTRS = {
    "key": "key",
    "name": "name",
    "category": "cat",
    "docs": "doc",
    "source": "src",
    "note": "note",
    "fields": "fields",
}
SOURCES = {"ibm-docs", "agent-template", "free", "user"}
OS_VALUES = {"linux", "aix", "windows", "solaris", "macos", "ibmi", "zos"}
NESTED = {"object", "objectList", "namedObjects"}


class CatalogError(ValueError):
    """Katalog kann nicht geladen werden."""


def default_dir():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "catalog")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _read_dir(directory):
    """Liest alle Dateien ein. Liefert (categories, fragments, plugins, errors)."""
    errors = []
    categories = []
    cat_file = os.path.join(directory, "categories.json")
    if os.path.exists(cat_file):
        try:
            categories = _read(cat_file).get("categories", [])
        except ValueError as e:
            errors.append("categories.json: %s" % e)
    fragments = {}
    fdir = os.path.join(directory, "fragments")
    if os.path.isdir(fdir):
        for name in sorted(os.listdir(fdir)):
            if name.endswith(".json"):
                try:
                    fragments[name[:-5]] = _read(os.path.join(fdir, name)).get("fields", [])
                except ValueError as e:
                    errors.append("fragments/%s: %s" % (name, e))
    plugins = []
    pdir = os.path.join(directory, "plugins")
    if not os.path.isdir(pdir):
        raise CatalogError("Kein Plugin-Verzeichnis gefunden: %s" % pdir)
    for name in sorted(os.listdir(pdir)):
        if not name.endswith(".json"):
            continue
        try:
            data = _read(os.path.join(pdir, name))
        except ValueError as e:
            errors.append("plugins/%s: ungültiges JSON: %s" % (name, e))
            continue
        plugins.append((name, data))
    return categories, fragments, plugins, errors


def _expand(fields, fragments, where, errors, depth=0):
    """Löst {"$ref": …} in Feldlisten auf (als Listeneintrag oder als 'fields')."""
    if depth > 10:
        errors.append("%s: Fragment-Verweise zu tief verschachtelt" % where)
        return []
    if isinstance(fields, dict) and "$ref" in fields:
        fields = [fields]
    if not isinstance(fields, list):
        errors.append("%s: 'fields' muss eine Liste sein" % where)
        return []
    out = []
    for f in fields:
        if isinstance(f, dict) and set(f) == {"$ref"}:
            ref = f["$ref"]
            if ref not in fragments:
                errors.append("%s: unbekanntes Fragment '%s'" % (where, ref))
                continue
            out.extend(
                _expand(copy.deepcopy(fragments[ref]), fragments, where + " → " + ref, errors, depth + 1)
            )
            continue
        f = dict(f)
        if "fields" in f:
            f["fields"] = _expand(f["fields"], fragments, "%s.%s" % (where, f.get("key")), errors, depth)
        if "alternatives" in f and isinstance(f["alternatives"], list):
            alts = []
            for a in f["alternatives"]:
                a = dict(a)
                if "fields" in a:
                    a["fields"] = _expand(
                        a["fields"], fragments, "%s.%s" % (where, f.get("key")), errors, depth
                    )
                alts.append(a)
            f["alternatives"] = alts
        out.append(f)
    return out


def _check_fields(fields, where, errors, in_alt=False):
    seen = set()
    for f in fields:
        if not isinstance(f, dict):
            errors.append("%s: Feld ist kein Objekt" % where)
            continue
        key = f.get("key")
        path = "%s.%s" % (where, key)
        unknown = set(f) - set(FIELD_ATTRS)
        if unknown:
            errors.append("%s: unbekannte Attribute %s" % (path, ", ".join(sorted(unknown))))
        if not in_alt:
            if not key or not isinstance(key, str):
                errors.append("%s: 'key' fehlt" % where)
            elif key in seen:
                errors.append("%s: doppelter Schlüssel" % path)
            seen.add(key)
        t = f.get("type")
        if t not in TYPES:
            errors.append("%s: unbekannter Typ '%s' (erlaubt: %s)" % (path, t, ", ".join(TYPES)))
            continue
        if t == "enum" and not (isinstance(f.get("options"), list) and f["options"]):
            errors.append("%s: enum braucht 'options'" % path)
        if t in NESTED:
            if not isinstance(f.get("fields"), list) or not f["fields"]:
                errors.append("%s: Typ %s braucht 'fields'" % (path, t))
            else:
                _check_fields(f["fields"], path, errors)
        if t == "oneOf":
            alts = f.get("alternatives")
            if not isinstance(alts, list) or len(alts) < 2:
                errors.append("%s: oneOf braucht mindestens zwei 'alternatives'" % path)
            else:
                for a in alts:
                    if a.get("type") not in ("stringList", "object"):
                        errors.append("%s: oneOf-Alternativen müssen stringList oder object sein" % path)
                    if not a.get("label"):
                        errors.append("%s: Alternative ohne 'label'" % path)
                    _check_fields([dict(a, key=key)], path, errors, in_alt=True)
        if "valueType" in f and f["valueType"] not in TYPES:
            errors.append("%s: unbekannter valueType '%s'" % (path, f["valueType"]))
        if "os" in f:
            bad = [o for o in (f["os"] if isinstance(f["os"], list) else [f["os"]]) if o not in OS_VALUES]
            if bad or not isinstance(f["os"], list):
                errors.append("%s: 'os' muss eine Liste aus %s sein" % (path, ", ".join(sorted(OS_VALUES))))


def _to_internal(f):
    o = {}
    for k, v in f.items():
        nk = FIELD_ATTRS[k]
        if k == "type" or k == "valueType":
            v = TYPES[v]
        elif k == "fields":
            v = [_to_internal(x) for x in v]
        elif k == "alternatives":
            v = [_to_internal(x) for x in v]
        o[nk] = v
    return o


def _process(directory):
    categories, fragments, raw, errors = _read_dir(directory)
    plugins, keys = [], set()
    for fname, p in raw:
        where = "plugins/" + fname
        unknown = set(p) - set(PLUGIN_ATTRS)
        if unknown:
            errors.append("%s: unbekannte Attribute %s" % (where, ", ".join(sorted(unknown))))
        key = p.get("key")
        if not key or not p.get("name") or not p.get("category"):
            errors.append("%s: 'key', 'name' und 'category' sind Pflicht" % where)
            continue
        if fname[:-5] != key:
            errors.append("%s: Dateiname muss dem Schlüssel entsprechen (%s.json)" % (where, key))
        if key in keys:
            errors.append("%s: Schlüssel %s mehrfach vorhanden" % (where, key))
        keys.add(key)
        if categories and p["category"] not in categories:
            errors.append("%s: Kategorie '%s' fehlt in categories.json" % (where, p["category"]))
        if p.get("source", "free") not in SOURCES:
            errors.append("%s: source muss eine von %s sein" % (where, ", ".join(sorted(SOURCES))))
        fields = _expand(p.get("fields", []), fragments, where, errors)
        _check_fields(fields, where, errors)
        p = dict(p, fields=fields)
        p.setdefault("source", "free" if not fields else "user")
        plugins.append(p)
    order = {c: i for i, c in enumerate(categories)}
    plugins.sort(key=lambda p: (order.get(p["category"], len(order)), p["name"].lower()))
    return categories, plugins, errors


def validate_catalog(directory=None):
    """Liefert eine Liste von Fehlermeldungen (leer = Katalog ist in Ordnung)."""
    try:
        return _process(directory or default_dir())[2]
    except CatalogError as e:
        return [str(e)]


def load_catalog(directory=None, strict=True):
    """Lädt den Katalog in interner Form. Liefert (plugins, categories, errors)."""
    categories, plugins, errors = _process(directory or default_dir())
    if errors and strict:
        raise CatalogError("Katalog fehlerhaft:\n  " + "\n  ".join(errors))
    internal = []
    for p in plugins:
        o = {PLUGIN_ATTRS[k]: v for k, v in p.items() if k != "fields"}
        o["fields"] = [_to_internal(f) for f in p["fields"]]
        internal.append(o)
    return internal, categories, errors
