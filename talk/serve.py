"""Serve the slides on localhost:8500 without caching (design_slides.md S9).

Python's plain http.server lets the browser keep an old slides.js, so an edit does not show
until a hard reload. This one tells the browser not to keep anything.
"""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class NoCache(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


if __name__ == "__main__":
    slides = Path(__file__).parent / "slides"
    server = ThreadingHTTPServer(("localhost", 8500), partial(NoCache, directory=str(slides)))
    print("Slides on http://localhost:8500")
    server.serve_forever()
