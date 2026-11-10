"""Dateizugriffe für Öffnen, Verzeichnisliste und Speichern."""

import datetime
import os
import shutil

from .importer import import_yaml


def _abs(p):
    return os.path.abspath(os.path.expanduser(p or "."))


def open_file(path, catalog_by_key):
    p = _abs(path)
    if os.path.isdir(p):
        raise ValueError("%s ist ein Verzeichnis" % p)
    with open(p, encoding="utf-8") as fh:
        res = import_yaml(fh.read(), catalog_by_key)
    res["path"] = p
    return res


def list_dir(d):
    d = _abs(d or os.getcwd())
    if not os.path.isdir(d):
        d = os.path.dirname(d) if os.path.isdir(os.path.dirname(d)) else os.getcwd()
    entries = []
    try:
        for name in sorted(os.listdir(d), key=str.lower):
            if name.startswith("."):
                continue
            full = os.path.join(d, name)
            if os.path.isdir(full):
                entries.append({"name": name, "type": "dir"})
            elif name.lower().endswith((".yaml", ".yml")):
                try:
                    st = os.stat(full)
                    entries.append(
                        {
                            "name": name,
                            "type": "file",
                            "size": st.st_size,
                            "mtime": datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
                        }
                    )
                except OSError:
                    pass
        err = None
    except OSError as e:
        err = str(e)
    parent = os.path.dirname(d)
    return {"dir": d, "parent": parent if parent != d else None, "entries": entries, "error": err}


def save_file(path, text, overwrite=False, backup=True):
    target = _abs(path)
    if os.path.isdir(target):
        return {"ok": False, "message": "%s ist ein Verzeichnis – bitte einen Dateinamen angeben." % target}
    if os.path.exists(target) and not overwrite:
        return {"ok": False, "exists": True, "path": target, "message": "%s existiert bereits." % target}
    try:
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        bak = None
        if os.path.exists(target) and backup:
            bak = target + ".bak-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            shutil.copy2(target, bak)
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(text)
    except OSError as e:
        return {"ok": False, "message": "Speichern fehlgeschlagen: %s" % e}
    msg = "Gespeichert: %s" % target
    if bak:
        msg += " (vorherige Version: %s)" % os.path.basename(bak)
    return {"ok": True, "message": msg, "path": target}
