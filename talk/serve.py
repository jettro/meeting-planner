"""Serve the slides on localhost:8500 without caching (design_slides.md S9).

Python's plain http.server lets the browser keep an old slides.js, so an edit does not show
until a hard reload. This one tells the browser not to keep anything.

It also serves the team's catalog under /catalog/ - the YAML cards only, read-only - so the
configuration slides show the files that run (design_config_and_navigation.md Q2).
SLIDES_PORT picks another port, for a second copy beside the one on 8500.
"""

import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).parent
SLIDES = HERE / "slides"
CATALOG = (HERE.parent / "agents" / "catalog").resolve()


class NoCache(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def translate_path(self, path: str) -> str:
        if not path.startswith("/catalog/"):
            return super().translate_path(path)
        wanted = (CATALOG / path.split("?", 1)[0].removeprefix("/catalog/")).resolve()
        # Only a .yaml file inside the catalog; anything else is not found.
        if CATALOG in wanted.parents and wanted.suffix == ".yaml":
            return str(wanted)
        return str(CATALOG / "__not_found__")


if __name__ == "__main__":
    port = int(os.environ.get("SLIDES_PORT", "8500"))
    server = ThreadingHTTPServer(("localhost", port), partial(NoCache, directory=str(SLIDES)))
    print(f"Slides on http://localhost:{port}")
    server.serve_forever()
