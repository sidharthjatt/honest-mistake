"""Serve the scan page the way GitHub Pages caches it, for verify/_verify_selffix.html.

    python3 verify/selffix_server.py 8350
    open http://127.0.0.1:8350/verify/_verify_selffix.html

The page under test is docs/ as it is on disk, served under
/r/<nonce>/honest-mistake/. Each trial picks a new nonce, so its URLs start
with nothing in the browser's cache.

Two builds are served from the same files:
- B is docs/ unchanged.
- A is docs/ with every module's stamp line rewritten to STAMP_A. It is a
  consistent build of its own, so the page starts on it.

Every response carries an ETag taken from its content and gets a 304 on a
matching If-None-Match, like Pages. agent/parse.js is sent with max-age=600,
like Pages; every other file with max-age=0, so a reload revalidates it. A
trial loads A, switches to B and reloads. Everything but parse.js comes back
as B, while parse.js stays in the browser's cache as A. That is a mixed cache
made by real caching, not by an import map.

/ctl/ switches what is served:
- /ctl/set?to=A|B picks the build, and resets the two below.
- /ctl/pin?parse=A keeps serving A's parse.js whatever is asked, as a CDN
  still holding the old copy would.
- /ctl/loader?to=mutant serves B's scan.js with its refetch removed, so its
  self-fix reloads without fetching anything first.
- /ctl/info gives both stamps. /ctl/log returns the request log and clears it.

The mutant is made by deleting one exact statement from scan.js. If that
statement isn't there exactly once, this server exits instead of serving a
mutant that might not be one.
"""
import hashlib
import http.server
import json
import re
import sys
import threading
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
STAMP_A = "aaaaaaaaaaaa"
STAMP_LINE = re.compile(rb"\Aexport const BUILD = '([0-9a-f]{12})';\n")
REFETCH = (b"  await Promise.all([...MODULES, './scan.js'].map(path =>\n"
           b"    fetch(resolve(path), { cache: 'reload' }).catch(() => null)));\n")
TYPES = {"js": "text/javascript", "html": "text/html", "json": "application/json",
         "css": "text/css", "svg": "image/svg+xml", "png": "image/png"}

_loader = (DOCS / "scan.js").read_bytes()
if _loader.count(REFETCH) != 1:
    sys.exit("scan.js no longer contains the refetch statement exactly once; "
             "the mutant can't be made, so this server won't start.")
MUTANT_LOADER = _loader.replace(REFETCH, b"")
STAMP_B = STAMP_LINE.match(_loader).group(1).decode()

state = {"set": "A", "pin": None, "loader": "normal"}
log, lock = [], threading.Lock()


def stamped(rest):
    return rest in ("scan.js", "scan-page.js") or (
        rest.startswith("agent/") and rest.endswith(".js"))


def body_for(rest, build):
    if build == "B" and rest == "scan.js" and state["loader"] == "mutant":
        return MUTANT_LOADER
    path = (DOCS / rest).resolve()
    if DOCS not in path.parents or not path.is_file():
        return None
    body = path.read_bytes()
    if build == "A" and stamped(rest):
        body, n = STAMP_LINE.subn(f"export const BUILD = '{STAMP_A}';\n".encode(), body, count=1)
        if n != 1:
            raise RuntimeError(f"{rest} has no stamp line to rewrite")
    return body


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(url.query)
        if url.path == "/ctl/set":
            state.update(set=q["to"][0], pin=None, loader="normal")
            return self.plain(b"ok")
        if url.path == "/ctl/pin":
            state["pin"] = q["parse"][0]
            return self.plain(b"ok")
        if url.path == "/ctl/loader":
            state["loader"] = q["to"][0]
            return self.plain(b"ok")
        if url.path == "/ctl/info":
            return self.plain(json.dumps({"stampA": STAMP_A, "stampB": STAMP_B}).encode(),
                              "application/json")
        if url.path == "/ctl/log":
            with lock:
                body = json.dumps(log).encode()
                log.clear()
            return self.plain(body, "application/json")
        if url.path == "/verify/_verify_selffix.html":
            return self.plain((ROOT / "verify" / "_verify_selffix.html").read_bytes(), "text/html")

        parts = url.path.split("/", 4)
        if len(parts) < 5 or parts[1] != "r" or parts[3] != "honest-mistake":
            return self.plain(b"not found", code=404)
        rest = parts[4] or "index.html"
        build = state["set"]
        if rest == "agent/parse.js" and state["pin"]:
            build = state["pin"]
        entry = {"path": rest, "build": build, "inm": self.headers.get("If-None-Match"),
                 "cc": self.headers.get("Cache-Control")}
        with lock:
            log.append(entry)
        body = body_for(rest, build)
        if body is None:
            entry["status"] = 404
            return self.plain(b"not found", code=404)
        etag = '"' + hashlib.sha1(body).hexdigest()[:16] + '"'
        age = 600 if rest == "agent/parse.js" else 0
        if self.headers.get("If-None-Match") == etag:
            entry["status"] = 304
            self.send_response(304)
            self.send_header("ETag", etag)
            self.send_header("Cache-Control", f"max-age={age}")
            self.end_headers()
            return
        entry["status"] = 200
        self.send_response(200)
        self.send_header("Content-Type", TYPES.get(rest.rsplit(".", 1)[-1], "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("ETag", etag)
        self.send_header("Cache-Control", f"max-age={age}")
        self.end_headers()
        self.wfile.write(body)

    def plain(self, body, ctype="text/plain", code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()
