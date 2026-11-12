"""Mehrere configuration*.yaml so zusammenführen, wie der Instana-Agent sie auswertet.

Verhalten des Agenten (IBM-Doku „Creating multiple configuration files“, ergänzt durch Tests):

- zuerst configuration.yaml, danach alle configuration-<suffix>.yaml streng alphanumerisch
  (Zeichencode: configuration-aa.yaml vor configuration-bb.yaml, Großbuchstaben vor Kleinbuchstaben)
- Mappings werden verschachtelt zusammengeführt; bei gleichen Schlüsseln gewinnt die spätere Datei
- Listen werden ergänzt, nicht ersetzt (neue Einträge werden angehängt, Dubletten nicht doppelt)

base_first und lists bleiben als Parameter für Tests und Experimente.
"""

import os
import re

from .yamlio import load_yaml

AGENT_NAME = re.compile(r"^configuration(-[^/\\]+)?\.yaml$")
BASE = "configuration.yaml"


def sort_key(path, base_first=True):
    name = os.path.basename(path)
    if base_first and name == BASE:
        return ("", path)
    return (name, path)  # str-Vergleich = Zeichencode-Reihenfolge, Großbuchstaben vor Kleinbuchstaben


def order_files(paths, base_first=True):
    return sorted(paths, key=lambda p: sort_key(p, base_first))


class _Merger:
    def __init__(self, lists):
        self.lists = lists
        self.origin = {}  # Pfad-Tupel → Dateiname der zuletzt setzenden Datei
        self.history = {}  # Pfad-Tupel → [(datei, wert), ...] bei Überschreibungen

    def _mark(self, path, value, src):
        """Herkunft für alle Blätter unter path setzen."""
        if isinstance(value, dict):
            for k, v in value.items():
                self._mark(path + (k,), v, src)
            if not value:
                self.origin[path] = src
        else:
            self.origin[path] = src

    def merge(self, base, new, src, path=()):
        for k, v in new.items():
            p = path + (k,)
            if k not in base:
                base[k] = v
                self._mark(p, v, src)
                continue
            old = base[k]
            if isinstance(old, dict) and isinstance(v, dict):
                self.merge(old, v, src, p)
                continue
            if self.lists == "merge" and isinstance(old, list) and isinstance(v, list):
                added = [x for x in v if x not in old]
                if added:
                    base[k] = old + added
                    prev = self.origin.get(p)
                    self.origin[p] = prev if prev == src else "%s + %s" % (prev, src)
                continue
            if old != v:
                h = self.history.setdefault(p, [(self.origin.get(p) or self._origin_of(p), old)])
                h.append((src, v))
            base[k] = v
            self._clear(p)
            self._mark(p, v, src)

    def _origin_of(self, path):
        for q, s in self.origin.items():
            if q[: len(path)] == path:
                return s
        return "?"

    def _clear(self, path):
        for q in [q for q in self.origin if q[: len(path)] == path]:
            del self.origin[q]


def merge_files(paths, base_first=True, lists="merge", read=None):
    """paths: Dateipfade. read: optionale Funktion path → Text (für Tests).
    Ergebnis: dict mit order, data, origin, conflicts, warnings."""
    read = read or _read
    warnings = []
    order = []
    names = {}
    for p in order_files(paths, base_first):
        name = os.path.basename(p)
        entry = {"path": p, "name": name, "dir": os.path.dirname(p), "used": True, "note": ""}
        if not AGENT_NAME.match(name):
            entry["used"] = False
            entry["note"] = "Name passt nicht zu configuration.yaml bzw. configuration-<suffix>.yaml – der Agent liest die Datei nicht."
        elif name in names:
            entry["note"] = (
                "Gleicher Dateiname wie %s – auf dem Agenten kann es nur eine Datei dieses Namens geben."
                % names[name]
            )
            warnings.append("„%s“ ist mehrfach ausgewählt." % name)
        names.setdefault(name, p)
        order.append(entry)

    m = _Merger(lists)
    data = {}
    for e in order:
        if not e["used"]:
            continue
        try:
            doc, w = load_yaml(read(e["path"]), strict=False)
        except Exception as ex:  # noqa: BLE001
            e["used"] = False
            e["note"] = "Nicht lesbar: %s" % ex
            warnings.append("%s: %s" % (e["name"], ex))
            continue
        for x in w:
            warnings.append("%s: %s" % (e["name"], x))
        if doc is None:
            e["note"] = e["note"] or "leer"
            continue
        if not isinstance(doc, dict):
            e["used"] = False
            e["note"] = "Kein YAML-Mapping auf oberster Ebene – wird übersprungen."
            continue
        e["keys"] = list(doc.keys())
        m.merge(data, doc, _label(e, order))

    conflicts = [
        {"path": list(p), "steps": [{"file": f, "value": v} for f, v in h]}
        for p, h in sorted(m.history.items(), key=lambda kv: [str(x) for x in kv[0]])
    ]
    return {
        "order": order,
        "data": data,
        "origin": m.origin,
        "conflicts": conflicts,
        "warnings": warnings,
    }


def _label(entry, order):
    """Dateiname, bei gleichnamigen Dateien mit Verzeichnis."""
    same = [e for e in order if e["name"] == entry["name"]]
    if len(same) > 1:
        return "%s (%s)" % (entry["name"], os.path.basename(entry["dir"]) or entry["dir"])
    return entry["name"]


def _read(path):
    with open(os.path.expanduser(path), encoding="utf-8") as fh:
        return fh.read()


# ---------------- Ausgabe als YAML mit Herkunftskommentaren ----------------

_PLAIN = re.compile(r"^[A-Za-z0-9_./][A-Za-z0-9_./ \-]*$")
_SPECIAL = re.compile(r"^(true|false|yes|no|on|off|null|~|y|n|[-+]?[0-9][0-9_.eE+-]*)$", re.I)


def scalar(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if _PLAIN.match(s) and not _SPECIAL.match(s) and not s.endswith(" "):
        return s
    return "'" + s.replace("'", "''") + "'"


def _key(k):
    s = str(k)
    return s if re.match(r"^[A-Za-z0-9_.\-/]+$", s) and not _SPECIAL.match(s) else scalar(s)


def to_yaml(data, origin=None, history=None):
    """Erzeugt YAML; mit origin werden Blätter mit '# <datei>' kommentiert,
    mit history (Pfad-Tupel → Schritte) zusätzlich das Überschriebene."""
    out = []
    origin = origin or {}
    history = history or {}

    def note(path):
        if not origin:
            return ""
        src = origin.get(path)
        if src is None:
            return ""
        h = history.get(path)
        if h and len(h) > 1:
            prev = ", ".join("%s: %s" % (f, _short(v)) for f, v in h[:-1])
            return "  # %s  ⟵ überschreibt %s" % (src, prev)
        return "  # %s" % src

    def emit(v, ind, path):
        pad = " " * ind
        if isinstance(v, dict):
            for k, x in v.items():
                p = path + (k,)
                if isinstance(x, dict) and x:
                    out.append("%s%s:" % (pad, _key(k)))
                    emit(x, ind + 2, p)
                elif isinstance(x, list) and x:
                    out.append("%s%s:%s" % (pad, _key(k), note(p)))
                    emit(x, ind + 2, p)
                else:
                    empty = "{}" if isinstance(x, dict) else "[]" if isinstance(x, list) else scalar(x)
                    out.append("%s%s: %s%s" % (pad, _key(k), empty, note(p)))
        elif isinstance(v, list):
            for x in v:
                if isinstance(x, (dict, list)) and x:
                    sub = []
                    _emit_into(x, sub)
                    out.append("%s- %s" % (pad, sub[0]))
                    out.extend("%s  %s" % (pad, s) for s in sub[1:])
                else:
                    out.append("%s- %s" % (pad, scalar(x) if not isinstance(x, (dict, list)) else "{}" if isinstance(x, dict) else "[]"))

    def _emit_into(x, sub):
        saved = out[:]
        del out[:]
        emit(x, 0, ("\0liste",))  # eigener Präfix: keine Herkunftskommentare in Listeneinträgen
        sub.extend(out)
        out[:] = saved

    emit(data, 0, ())
    return "\n".join(out) + ("\n" if out else "")


def _short(v):
    if isinstance(v, list) and all(not isinstance(x, (dict, list)) for x in v):
        s = "[" + ", ".join(scalar(x) for x in v) + "]"
    else:
        s = scalar(v) if not isinstance(v, (dict, list)) else ("{…}" if isinstance(v, dict) else "[…]")
    return s if len(s) <= 40 else s[:37] + "…"


def evaluate(paths, base_first=True, lists="merge", read=None):
    """Für die API: Ergebnis als JSON-taugliches dict mit YAML-Text (mit und ohne Herkunft)."""
    r = merge_files(paths, base_first, lists, read)
    hist = {tuple(c["path"]): [(s["file"], s["value"]) for s in c["steps"]] for c in r["conflicts"]}
    for c in r["conflicts"]:
        for st in c["steps"]:
            st["text"] = _short(st["value"])
            del st["value"]
    return {
        "ok": True,
        "order": r["order"],
        "conflicts": r["conflicts"],
        "warnings": r["warnings"],
        "yaml": to_yaml(r["data"]),
        "annotated": to_yaml(r["data"], r["origin"], hist),
        "files": sum(1 for e in r["order"] if e["used"]),
    }
