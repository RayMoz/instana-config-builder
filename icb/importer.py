"""Abbildung einer geparsten configuration.yaml auf den Katalog (Formularwerte)."""

from .yamlio import dump as _dump, load_yaml


def _scalar_str(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return ""
    return str(v)


def _is_scalar(v):
    return v is None or isinstance(v, (str, int, float, bool))


def _raw(v):
    return {"$raw": _dump(v)}


def _walk(fields, data):
    """Ordnet ein geparstes Dict den Katalogfeldern zu.
    Liefert (values, rest) – rest enthält unbekannte Schlüssel."""
    fmap = {f["k"]: f for f in fields}
    values, rest = {}, {}
    for k, v in data.items():
        f = fmap.get(str(k))
        if f is None:
            rest[k] = v
        else:
            values[f["k"]] = _convert(f, v)
    return values, rest


def _convert(f, v):
    t = f["t"]
    if t in ("str", "secret", "enum", "int"):
        return _scalar_str(v) if _is_scalar(v) else _raw(v)
    if t == "bool":
        return _scalar_str(v) if isinstance(v, bool) else _raw(v)
    if t == "list":
        if isinstance(v, list) and all(_is_scalar(x) for x in v):
            return [_scalar_str(x) for x in v]
        return _raw(v)
    if t == "kv":
        if isinstance(v, dict) and all(_is_scalar(x) for x in v.values()):
            return [[str(k), _scalar_str(x)] for k, x in v.items()]
        return _raw(v)
    if t == "obj":
        if isinstance(v, dict):
            vals, rest = _walk(f["f"], v)
            return _raw(v) if rest else vals
        return _raw(v)
    if t == "objlist":
        if isinstance(v, list) and all(isinstance(x, dict) for x in v):
            items = []
            for x in v:
                vals, rest = _walk(f["f"], x)
                if rest:
                    return _raw(v)
                items.append(vals)
            return items
        return _raw(v)
    if t == "map":
        if isinstance(v, dict) and all(isinstance(x, dict) or x is None for x in v.values()):
            items = []
            for name, x in v.items():
                vals, rest = _walk(f["f"], x or {})
                if rest:
                    return _raw(v)
                items.append({"name": str(name), "values": vals})
            return items
        return _raw(v)
    if t == "alt":
        for alt in f["alts"]:
            if alt["t"] == "list" and isinstance(v, list) and all(_is_scalar(x) for x in v):
                return [_scalar_str(x) for x in v]
            if alt["t"] == "obj" and isinstance(v, dict):
                vals, rest = _walk(alt["f"], v)
                if not rest:
                    return vals
        return _raw(v)
    # yaml / unbekannt
    return {"$raw": _dump(v)}


def import_yaml(text, catalog_by_key):
    data, warnings = load_yaml(text, strict=False)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError("Die Datei enthält kein YAML-Mapping auf oberster Ebene.")
    plugins = []
    for key, body in data.items():
        key = str(key)
        entry = catalog_by_key.get(key)
        if entry is None:
            plugins.append(
                {"key": key, "custom": True, "values": {}, "extra": "" if body is None else _dump(body)}
            )
            continue
        if isinstance(body, dict):
            values, rest = _walk(entry["fields"], body)
            extra = _dump(rest) if rest else ""
        else:
            values, extra = {}, "" if body is None else _dump(body)
        plugins.append({"key": key, "values": values, "extra": extra})
    return {"plugins": plugins, "warnings": warnings}


def validate_yaml(text, catalog_by_key):
    try:
        data, _ = load_yaml(text, strict=True)
    except Exception as e:  # noqa: BLE001  (yaml.YAMLError oder MiniYAMLError)
        return {"ok": False, "message": str(e)}
    if data is None:
        return {"ok": True, "message": "Leere Konfiguration."}
    if not isinstance(data, dict):
        return {"ok": False, "message": "Oberste Ebene ist kein Mapping."}
    unknown = [k for k in data if str(k) not in catalog_by_key]
    msg = "YAML ist gültig: %d Abschnitt(e)." % len(data)
    if unknown:
        msg += " Nicht im Katalog: " + ", ".join(map(str, unknown))
    return {"ok": True, "message": msg}
