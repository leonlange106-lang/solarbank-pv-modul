"""Statischer Server fuer den Pruefstand der Solarbank-App.

ES-Module laden nicht ueber file:// - der Browser verweigert den Import mit
einem CORS-Fehler. Deshalb dieser Server. Er liefert das Repo-Wurzelverzeichnis
aus, damit tools/bench/index.html die Module unter
custom_components/solarbank_app/www/ erreicht.

Aufruf:
    python tools/bench/serve.py            Port 8765
    python tools/bench/serve.py 9000       eigener Port

Dann im Browser: http://127.0.0.1:8765/tools/bench/index.html

Bindet bewusst nur an 127.0.0.1. Der Pruefstand enthaelt zwar keine
Zugangsdaten, hat aber im Netz nichts zu suchen.
"""
from __future__ import annotations

import functools
import http.server
import pathlib
import socketserver
import sys

WURZEL = pathlib.Path(__file__).resolve().parents[2]


class Handler(http.server.SimpleHTTPRequestHandler):
    """Liefert aus dem Repo, mit korrekten MIME-Typen und ohne Cache."""

    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".json": "application/json",
        ".svg": "image/svg+xml",
    }

    def end_headers(self) -> None:
        # Ohne das prueft man nach einer Aenderung die alte Datei - genau der
        # Fehler, der bei Custom Panels ohnehin schon lauert.
        self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()

    def log_message(self, format: str, *args) -> None:
        # Nur Fehler melden; 200er waeren hier nur Rauschen.
        if len(args) > 1 and str(args[1]).startswith(("4", "5")):
            sys.stderr.write("  %s %s\n" % (args[0], args[1]))


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    handler = functools.partial(Handler, directory=str(WURZEL))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", port), handler) as srv:
        print(f"Pruefstand: http://127.0.0.1:{port}/tools/bench/index.html")
        print(f"Wurzel:     {WURZEL}")
        print("Beenden mit Strg+C")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\nbeendet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
