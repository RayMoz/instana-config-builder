"""instana-fleet-Befehle für eine Konfigurationsdatei erzeugen (nur anzeigen, nicht ausführen).

Grundlage: Instana Agent Fleet Management (Preview). Ablauf:
  1. instana-fleet import-config --type com.ibm.instana.agent --include <datei>
       --config-name <name> --config-version <version>      → gibt die Configuration-ID aus
  2. instana-fleet update-config --type com.ibm.instana.agent --tag <key=wert>
       --configuration-id <ID>                               → verteilt an alle Agenten mit dem Tag
Server und Token liest die CLI aus INSTANA_SERVER (Hostname ohne https://) und INSTANA_API_TOKEN.
"""

import os
import re

from .repo import AGENT_NAME, extract

AGENT_TYPE = "com.ibm.instana.agent"
_SEMVER = re.compile(r"^\d+\.\d+\.\d+([-+][0-9A-Za-z.-]+)?$")
_NAME_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_SELECTOR = re.compile(r"^([^=\s]+)=(.+)$")


def sh(s):
    """Für die Shell in einfache Anführungszeichen setzen."""
    s = str(s)
    if re.match(r"^[A-Za-z0-9_./:=@%+-]+$", s):
        return s
    return "'" + s.replace("'", "'\\''") + "'"


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")


def suggest(path, repo_root=None, text=None):
    """Vorschläge für Konfigurationsname und Tag-Selektoren.
    dirSelectors: Verzeichnisse der Form key=wert unterhalb des Repositorys (in Pfadreihenfolge);
    selectors: diese plus key=wert-Tags aus com.instana.plugin.host.tags."""
    path = os.path.abspath(os.path.expanduser(path))
    name = os.path.basename(path)
    selectors = []
    dir_selectors = []
    in_repo = False
    if repo_root:
        root = os.path.abspath(os.path.expanduser(repo_root))
        try:
            in_repo = os.path.commonpath([path, root]) == root
        except ValueError:
            in_repo = False
        if in_repo:
            for seg in os.path.relpath(os.path.dirname(path), root).split(os.sep):
                if _SELECTOR.match(seg) and seg not in dir_selectors:
                    dir_selectors.append(seg)
            selectors = list(dir_selectors)
    if text is not None:
        try:
            for t in extract(text)["tags"]:
                m = re.match(r"^\s*([^=:\s]+)\s*[=:]\s*(.+?)\s*$", t)
                if m:
                    s = "%s=%s" % (m.group(1), m.group(2))
                    if s not in selectors:
                        selectors.append(s)
        except Exception:  # noqa: BLE001 – Vorschläge sind optional
            pass
    m = re.match(r"^configuration(?:-(.+))?\.ya?ml$", name)
    suffix = m.group(1) if m and m.group(1) else ("basis" if m else os.path.splitext(name)[0])
    parts = [_SELECTOR.match(s).group(2) for s in dir_selectors]
    config_name = "-".join(p for p in (_slug(x) for x in parts + [suffix]) if p) or "agent-config"
    return {"configName": config_name, "selectors": selectors, "dirSelectors": dir_selectors, "inRepo": in_repo}


def commands(path, config_name, version, tags, server="", dir_selectors=()):
    """Erzeugt das Befehlsskript und Hinweise."""
    path = os.path.abspath(os.path.expanduser(path))
    name = os.path.basename(path)
    warnings = []
    if not AGENT_NAME.match(name):
        warnings.append(
            "„%s“: Der Agent akzeptiert nur configuration.yaml oder configuration-<suffix>.yaml – "
            "import-config übernimmt den Dateinamen." % name
        )
    if not os.path.isfile(path):
        warnings.append("Die Datei existiert nicht: %s" % path)
    config_name = (config_name or "").strip()
    if not config_name:
        warnings.append("Bitte einen Konfigurationsnamen angeben.")
    elif not _NAME_OK.match(config_name):
        warnings.append("Konfigurationsname besser nur aus Buchstaben, Ziffern, . _ - bilden.")
    version = (version or "").strip()
    if not _SEMVER.match(version):
        warnings.append("Version bitte im Format 1.0.0 angeben (Semantic Versioning).")
    tags = [t.strip() for t in tags or [] if t and t.strip()]
    bad = [t for t in tags if not _SELECTOR.match(t)]
    if bad:
        warnings.append("Tag-Selektor im Format key=wert angeben: %s" % ", ".join(bad))
    if not tags:
        warnings.append("Ohne Tag-Selektor weiß update-config nicht, welche Agenten die Konfiguration erhalten.")
    unused = [d for d in dir_selectors if d not in tags]
    if tags and unused:
        warnings.append(
            "Die Datei liegt unter %s, der Selektor lässt %s weg – update-config erreicht dann auch "
            "Agenten außerhalb dieser Gruppe." % ("/".join(dir_selectors), ", ".join(unused))
        )
    if len(tags) > 1:
        warnings.append("Mehrere --tag sind in der Preview-Doku nicht beschrieben – bitte in der Sandbox prüfen.")
    server = re.sub(r"^https?://", "", (server or "").strip()).rstrip("/")

    srv = ["  --server %s \\" % sh(server)] if server else []
    tag_lines = ["  --tag %s \\" % sh(t) for t in tags] or ["  --tag <key=wert> \\"]
    cn = sh(config_name or "<name>")
    ver = sh(version or "<version>")
    lines = [
        "# Erzeugt mit dem Instana configuration.yaml Builder – Befehle vor dem Ausführen prüfen.",
        "# Voraussetzung:",
        "#   export INSTANA_SERVER=%s   # Hostname ohne https://"
        % (sh(server) if server else "instana.example.com"),
        "#   export INSTANA_API_TOKEN=…   # Token mit Fleet-Management-Rechten",
        "",
        "# 1. Konfiguration hochladen (gibt die Configuration-ID aus)",
        "instana-fleet import-config \\",
        *srv,
        "  --type %s \\" % AGENT_TYPE,
        "  --include %s \\" % sh(path),
        "  --config-name %s \\" % cn,
        "  --config-version %s" % ver,
        "",
        "# 2. Configuration-ID ermitteln – aus der Ausgabe von Schritt 1 übernehmen oder nachschlagen:",
        "instana-fleet list-configs%s --type %s" % (" --server %s" % sh(server) if server else "", AGENT_TYPE),
        "# ungeprüft (Ausgabeformat der Preview): ID per jq herausfiltern",
        "# export CONFIGURATION_ID=$(instana-fleet list-configs%s --type %s \\"
        % (" --server %s" % sh(server) if server else "", AGENT_TYPE),
        "#   | jq -r '.[] | select(.name==\"%s\" and .version==\"%s\") | .configuration_id')"
        % (config_name or "<name>", version or "<version>"),
        "",
        "# 3. An alle Agenten mit dem Tag verteilen",
        "instana-fleet update-config \\",
        *srv,
        "  --type %s \\" % AGENT_TYPE,
        *tag_lines,
        '  --configuration-id "${CONFIGURATION_ID:?Configuration-ID aus Schritt 1 oder 2 setzen}"',
        "",
        "# Rollback: update-config mit der Configuration-ID einer früheren Version erneut ausführen.",
        "",
    ]
    return {"script": "\n".join(lines), "warnings": warnings}


def plan(body, repo_root):
    """Für die API: Vorschläge (bei leeren Feldern) und Skript."""
    path = os.path.abspath(os.path.expanduser(body.get("path") or ""))
    text = None
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        text = body.get("yaml")
    sug = suggest(path, repo_root, text)
    tags = body.get("tags")
    if tags is None:
        tags = sug["dirSelectors"] or sug["selectors"][:1]
    res = commands(
        path,
        body.get("configName") if body.get("configName") is not None else sug["configName"],
        body.get("version") or "1.0.0",
        tags,
        body.get("server", ""),
        sug["dirSelectors"],
    )
    res.update({"ok": True, "suggest": sug, "path": path, "tags": tags})
    return res
