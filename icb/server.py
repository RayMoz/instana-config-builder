"""Lokaler HTTP-Server: liefert die Web-UI aus und stellt die JSON-API bereit."""

import argparse
import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import VERSION
from .catalog import CatalogError, default_dir, load_catalog
from .files import list_dir, open_file, save_file
from .importer import import_yaml, validate_yaml
from .fleet import plan as fleet_plan
from .merge import evaluate
from .repo import Repo
from .yamlio import BACKEND

WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
}


class Handler(BaseHTTPRequestHandler):
    server_version = "InstanaConfigBuilder/" + VERSION
    cfg = {}  # input, output
    repo = None  # Repo
    catalog = []  # interne Form
    categories = []
    by_key = {}

    def log_message(self, fmt, *args):  # ruhig bleiben
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    def _same_origin(self):
        # Schutz gegen Anfragen fremder Webseiten an den lokalen Server
        origin = self.headers.get("Origin")
        host = self.headers.get("Host", "")
        return origin is None or origin.split("://", 1)[-1] == host

    def do_GET(self):
        u = urlparse(self.path)
        path, qs = u.path, parse_qs(u.query)
        if path in STATIC:
            name, ctype = STATIC[path]
            try:
                with open(os.path.join(WEB_DIR, name), "rb") as fh:
                    self._send(200, fh.read(), ctype)
            except OSError:
                self._send(500, "Datei fehlt: web/%s" % name, "text/plain; charset=utf-8")
        elif path == "/api/catalog":
            self._json(200, {"plugins": self.catalog, "categories": self.categories})
        elif path == "/api/info":
            initial, err = None, None
            if self.cfg.get("input"):
                try:
                    initial = open_file(self.cfg["input"], self.by_key)
                except Exception as e:  # noqa: BLE001
                    err = "%s: %s" % (self.cfg["input"], e)
            self._json(
                200,
                {
                    "version": VERSION,
                    "pyyaml": BACKEND == "PyYAML",
                    "output": os.path.abspath(
                        os.path.expanduser(self.cfg.get("output", "configuration.yaml"))
                    ),
                    "home": os.path.expanduser("~"),
                    "sep": os.sep,
                    "initial": initial,
                    "error": err,
                    "repo": self.repo.info(),
                },
            )
        elif path == "/api/ls":
            self._json(200, list_dir((qs.get("dir") or [""])[0]))
        else:
            self._send(404, "nicht gefunden", "text/plain; charset=utf-8")

    def do_POST(self):
        if not self._same_origin():
            self._json(403, {"ok": False, "message": "Fremder Ursprung abgelehnt."})
            return
        path = self.path.split("?", 1)[0]
        try:
            body = self._body()
        except Exception as e:  # noqa: BLE001
            self._json(400, {"ok": False, "message": "Ungültige Anfrage: %s" % e})
            return
        if path == "/api/validate":
            self._json(200, validate_yaml(body.get("yaml", ""), self.by_key))
        elif path == "/api/import":
            try:
                self._json(200, dict(ok=True, **import_yaml(body.get("yaml", ""), self.by_key)))
            except Exception as e:  # noqa: BLE001
                self._json(200, {"ok": False, "message": "Datei konnte nicht gelesen werden: %s" % e})
        elif path == "/api/open":
            try:
                self._json(200, dict(ok=True, **open_file(body.get("path", ""), self.by_key)))
            except Exception as e:  # noqa: BLE001
                self._json(200, {"ok": False, "message": "Datei konnte nicht geöffnet werden: %s" % e})
        elif path == "/api/save":
            self._json(
                200,
                save_file(
                    body.get("path") or self.cfg["output"],
                    body.get("yaml", ""),
                    overwrite=bool(body.get("overwrite")),
                    backup=body.get("backup", True),
                ),
            )
        elif path == "/api/merge":
            paths = [p for p in body.get("paths") or [] if isinstance(p, str) and p.strip()]
            if not paths:
                self._json(200, {"ok": False, "message": "Keine Dateien ausgewählt."})
                return
            try:
                self._json(
                    200,
                    evaluate([os.path.abspath(os.path.expanduser(p)) for p in paths]),
                )
            except Exception as e:  # noqa: BLE001
                self._json(200, {"ok": False, "message": "Auswertung fehlgeschlagen: %s" % e})
        elif path == "/api/fleet":
            if not body.get("path"):
                self._json(200, {"ok": False, "message": "Bitte die Konfiguration zuerst speichern."})
                return
            try:
                self._json(200, fleet_plan(body, self.repo.root))
            except Exception as e:  # noqa: BLE001
                self._json(200, {"ok": False, "message": str(e)})
        elif path == "/api/repo/target":
            try:
                self._json(200, dict(ok=True, **self.repo.target(body.get("yaml", ""), body.get("pattern"), body.get("name", ""))))
            except Exception as e:  # noqa: BLE001
                self._json(200, {"ok": False, "message": str(e)})
        elif path == "/api/repo/save":
            try:
                self._json(
                    200,
                    self.repo.save(
                        body.get("yaml", ""),
                        body.get("pattern"),
                        overwrite=bool(body.get("overwrite")),
                        backup=body.get("backup", True),
                        name=body.get("name", ""),
                    ),
                )
            except Exception as e:  # noqa: BLE001
                self._json(200, {"ok": False, "message": str(e)})
        else:
            self._json(404, {"ok": False, "message": "Unbekannter Endpunkt"})


def make_server(port=0, catalog_dir=None, input_path=None, output="configuration.yaml", repo="repository"):
    """Erzeugt den Server (für Start und Tests)."""
    plugins, categories, _ = load_catalog(catalog_dir)
    handler = type(
        "BoundHandler",
        (Handler,),
        {
            "cfg": {"input": input_path, "output": input_path or output},
            "repo": Repo(repo),
            "catalog": plugins,
            "categories": categories,
            "by_key": {p["key"]: p for p in plugins},
        },
    )
    return ThreadingHTTPServer(("127.0.0.1", port), handler)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Instana configuration.yaml Builder (lokale Web-UI)")
    ap.add_argument("--input", help="bestehende configuration.yaml beim Start laden")
    ap.add_argument("--output", default="configuration.yaml", help="Standardpfad zum Speichern")
    ap.add_argument(
        "--repo", default="repository", help="Verzeichnis des Konfigurations-Repositorys (Standard: ./repository)"
    )
    ap.add_argument("--catalog", default=None, help="anderes Katalogverzeichnis (Standard: ./catalog)")
    ap.add_argument("--port", type=int, default=8765, help="Port (0 = automatisch)")
    ap.add_argument("--no-browser", action="store_true", help="Browser nicht öffnen")
    ap.add_argument("--version", action="version", version="%(prog)s " + VERSION)
    args = ap.parse_args(argv)

    try:
        httpd = make_server(args.port, args.catalog, args.input, args.output, args.repo)
    except CatalogError as e:
        print(str(e), file=sys.stderr)
        print("Tipp: python3 tools/validate_catalog.py zeigt alle Fehler.", file=sys.stderr)
        return 2
    except OSError as e:
        print(
            "Port %d ist belegt (%s). Mit --port 0 einen freien Port wählen." % (args.port, e),
            file=sys.stderr,
        )
        return 1
    h = httpd.RequestHandlerClass
    url = "http://127.0.0.1:%d/" % httpd.server_address[1]
    print("Instana configuration.yaml Builder %s läuft auf %s" % (VERSION, url))
    print(
        "Katalog: %s – %d Plugins (davon %d mit Optionen)"
        % (args.catalog or default_dir(), len(h.catalog), sum(1 for p in h.catalog if p["fields"]))
    )
    print("Repository: %s" % h.repo.root)
    print("YAML-Leser: %s" % (BACKEND if BACKEND == "PyYAML" else "eingebaut (PyYAML nicht installiert)"))
    print("Beenden mit Strg+C", flush=True)
    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nBeendet.")
    finally:
        httpd.server_close()
    return 0
