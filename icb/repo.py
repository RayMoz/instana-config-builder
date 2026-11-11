"""Konfigurations-Repository: legt configuration.yaml-Dateien in einer Verzeichnisstruktur ab,
deren Pfad sich aus Tags und Zone der Konfiguration ergibt.

Muster (Pfad relativ zum Repository, '/' trennt Verzeichnisse), Platzhalter:
  {tag:KEY}  Wert des Tags KEY=wert (auch KEY:wert) aus com.instana.plugin.host.tags
  {zone}     availability-zone aus com.instana.plugin.generic.hardware
  {tags}     alle übrigen Tags (die nicht schon über {tag:KEY} im Muster stehen), mit '-' verbunden;
             bei KEY=wert-Tags zählt nur der Wert
  {name}     frei eingegebener Name (z. B. availability-zone für configuration-availability-zone.yaml);
             leer → wie {tags}
Fehlt ein Wert, entfällt in Verzeichnissen die ganze Ebene, im Dateinamen nur der Platzhalter.

Hintergrund Fleet Management (Preview): Agenten werden per Tag-Selektor angesprochen
(instana-fleet update-config --tag team=Organisation). Die Standardstruktur benennt Verzeichnisse deshalb
wie die Selektoren (team=Organisation/env=production/). Auf dem Agenten erlaubt sind nur
configuration.yaml und configuration-<suffix>.yaml; import-config übernimmt den Dateinamen.
"""

import json
import os
import re

from .files import save_file
from .yamlio import load_yaml

DEFAULT_PATTERN = "team={tag:team}/env={tag:env}/configuration-{name}.yaml"
AGENT_NAME = re.compile(r"^configuration(-[A-Za-z0-9._-]+)?\.yaml$")
SETTINGS = ".icb-repo.json"
_PH = re.compile(r"\{(tag:[^{}]+|zone|tags|name)\}")
_UNSAFE = re.compile(r"[^\w.\-]+", re.UNICODE)


def _split_tag(t):
    """'env=prod' / 'env:prod' → ('env', 'prod'); 'production' → (None, 'production')."""
    m = re.match(r"^\s*([^=:\s]+)\s*[=:]\s*(.*?)\s*$", t)
    return (m.group(1), m.group(2)) if m else (None, t.strip())


def extract(text):
    """Liest Tags und Zone aus dem YAML-Text."""
    data, _ = load_yaml(text or "", strict=False)
    data = data if isinstance(data, dict) else {}
    host = data.get("com.instana.plugin.host") or {}
    hw = data.get("com.instana.plugin.generic.hardware") or {}
    raw = host.get("tags") if isinstance(host, dict) else None
    tags = [str(t) for t in raw if t is not None and str(t).strip()] if isinstance(raw, list) else []
    zone = hw.get("availability-zone") if isinstance(hw, dict) else None
    return {"tags": tags, "zone": str(zone).strip() if zone not in (None, "") else ""}


def _clean(v):
    v = _UNSAFE.sub("_", str(v).strip())
    return v.strip("._-") or ""


def render(pattern, info, name=""):
    """Bildet den relativen Pfad. Ergebnis: (relpath, used, missing)."""
    pattern = (pattern or DEFAULT_PATTERN).strip().replace("\\", "/")
    pairs = [_split_tag(t) for t in info["tags"]]
    kv = {}
    for k, v in pairs:
        if k is not None and k.lower() not in kv:
            kv[k.lower()] = v
    keys_in_pattern = {m[4:].strip().lower() for m in _PH.findall(pattern) if m.startswith("tag:")}
    rest = [v for k, v in pairs if k is None or k.lower() not in keys_in_pattern]
    used, missing = {}, []
    free_name = name or ""

    def value(name):
        if name == "zone":
            v = info["zone"]
        elif name in ("tags", "name"):
            v = "-".join(_clean(x) for x in rest if _clean(x))
            if name == "name" and _clean(free_name):
                v = _clean(free_name)
            used[name] = v
            if not v:
                missing.append(name)
            return v
        else:
            v = kv.get(name[4:].strip().lower(), "")
        v = _clean(v)
        used[name] = v
        if not v:
            missing.append(name)
        return v

    segs = []
    parts = pattern.split("/")
    for i, seg in enumerate(parts):
        n_missing = len(missing)
        s = _PH.sub(lambda m: value(m.group(1)), seg)
        if i < len(parts) - 1 and len(missing) > n_missing:
            continue  # Verzeichnisebene ohne Wert weglassen
        s = re.sub(r"([-_.])[-_.]*(?=[-_.])", "", s)  # doppelte Trenner nach leeren Werten
        s = re.sub(r"[-_]+(\.ya?ml)$", r"\1", s, flags=re.I)  # 'configuration-.yaml'
        s = s.strip(" -_")
        if s in ("", ".", ".."):
            continue
        segs.append(s)
    if not segs or re.fullmatch(r"\.ya?ml", segs[-1], re.I):
        segs = segs[:-1] + ["configuration.yaml"]
    if not re.search(r"\.ya?ml$", segs[-1], re.I):
        segs[-1] += ".yaml"
    return "/".join(segs), used, missing


class Repo:
    def __init__(self, root):
        self.root = os.path.abspath(os.path.expanduser(root))

    def settings(self):
        try:
            with open(os.path.join(self.root, SETTINGS), encoding="utf-8") as fh:
                s = json.load(fh)
        except (OSError, ValueError):
            s = {}
        return {"pattern": s.get("pattern") or DEFAULT_PATTERN}

    def store_pattern(self, pattern):
        if not pattern or pattern == self.settings()["pattern"]:
            return
        os.makedirs(self.root, exist_ok=True)
        with open(os.path.join(self.root, SETTINGS), "w", encoding="utf-8") as fh:
            json.dump({"pattern": pattern}, fh, ensure_ascii=False, indent=2)
            fh.write("\n")

    def info(self):
        return {"dir": self.root, "pattern": self.settings()["pattern"], "default": DEFAULT_PATTERN}

    def target(self, text, pattern=None, name=""):
        info = extract(text)
        rel, used, missing = render(pattern or self.settings()["pattern"], info, name)
        path = os.path.abspath(os.path.join(self.root, *rel.split("/")))
        if os.path.commonpath([path, self.root]) != self.root:
            raise ValueError("Pfad liegt außerhalb des Repositorys: %s" % rel)
        return {
            "rel": rel,
            "path": path,
            "exists": os.path.exists(path),
            "tags": info["tags"],
            "zone": info["zone"],
            "used": used,
            "missing": missing,
            "warnings": [] if AGENT_NAME.match(rel.rsplit("/", 1)[-1]) else [
                "Der Agent akzeptiert nur configuration.yaml oder configuration-<suffix>.yaml "
                "(Buchstaben, Ziffern, . _ -)."
            ],
        }

    def save(self, text, pattern=None, overwrite=False, backup=True, name=""):
        t = self.target(text, pattern, name)
        r = save_file(t["path"], text, overwrite=overwrite, backup=backup)
        if r.get("ok") and pattern:
            self.store_pattern(pattern)
        r["rel"] = t["rel"]
        return r
