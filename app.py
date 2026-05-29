import json
import os
import re
import string
import threading
from copy import deepcopy
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlparse


ROOT_DIR = Path(__file__).resolve().parent
STATIC_DIR = ROOT_DIR / "static"
DEFAULT_DATA_FILE = ROOT_DIR / "data" / "fonts.json"
GRID_ROWS = 16
GRID_COLS = 16

PERSIAN_CHARACTERS = [
    "ا",
    "ب",
    "پ",
    "ت",
    "ث",
    "ج",
    "چ",
    "ح",
    "خ",
    "د",
    "ذ",
    "ر",
    "ز",
    "ژ",
    "س",
    "ش",
    "ص",
    "ض",
    "ط",
    "ظ",
    "ع",
    "غ",
    "ف",
    "ق",
    "ک",
    "گ",
    "ل",
    "م",
    "ن",
    "و",
    "ه",
    "ی",
]
PERSIAN_FORMS = ["isolated", "initial", "medial", "final"]
ENGLISH_GROUPS = {
    "uppercase": list(string.ascii_uppercase),
    "lowercase": list(string.ascii_lowercase),
    "digit": list(string.digits),
}
TAB_ORDER = [
    "isolated",
    "initial",
    "medial",
    "final",
    "uppercase",
    "lowercase",
    "digit",
]


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def slugify(value):
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return slug or "font"


def blank_cells(rows=GRID_ROWS, cols=GRID_COLS):
    return [[0 for _ in range(cols)] for _ in range(rows)]


def make_glyph_id(script, character, form):
    return f"{script}-{ord(character):04x}-{form}"


def build_catalog():
    catalog = []
    for form in PERSIAN_FORMS:
        for character in PERSIAN_CHARACTERS:
            catalog.append(
                {
                    "id": make_glyph_id("fa", character, form),
                    "character": character,
                    "script": "persian",
                    "form": form,
                    "rows": GRID_ROWS,
                    "cols": GRID_COLS,
                }
            )
    for form, characters in ENGLISH_GROUPS.items():
        for character in characters:
            catalog.append(
                {
                    "id": make_glyph_id("en", character, form),
                    "character": character,
                    "script": "english",
                    "form": form,
                    "rows": GRID_ROWS,
                    "cols": GRID_COLS,
                }
            )
    return catalog


GLYPH_CATALOG = build_catalog()
GLYPH_LOOKUP = {glyph["id"]: glyph for glyph in GLYPH_CATALOG}


def with_cells(glyph, cells=None):
    payload = deepcopy(glyph)
    payload["cells"] = deepcopy(cells if cells is not None else blank_cells(glyph["rows"], glyph["cols"]))
    return payload


class FontStore:
    def __init__(self, data_file):
        self.data_file = Path(data_file)
        self._lock = threading.Lock()
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.data_file.exists():
            self._write_data({"fonts": []})

    def _read_data(self):
        with self.data_file.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _write_data(self, payload):
        with NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=self.data_file.parent) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            temp_name = handle.name
        os.replace(temp_name, self.data_file)

    def list_fonts(self):
        with self._lock:
            data = self._read_data()
            return [self._summarize(font) for font in data["fonts"]]

    def create_font(self, name, description=""):
        cleaned_name = (name or "").strip()
        if not cleaned_name:
            raise ValueError("Font name is required.")
        record = {
            "id": slugify(cleaned_name) + "-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
            "name": cleaned_name,
            "description": (description or "").strip(),
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "glyphs": {},
        }
        with self._lock:
            data = self._read_data()
            data["fonts"].append(record)
            self._write_data(data)
        return self.get_font(record["id"])

    def get_font(self, font_id):
        with self._lock:
            data = self._read_data()
            font = next((item for item in data["fonts"] if item["id"] == font_id), None)
            if font is None:
                raise KeyError(font_id)
            return self._expand(font)

    def update_glyphs(self, font_id, glyph_updates):
        if not isinstance(glyph_updates, dict) or not glyph_updates:
            raise ValueError("Glyph updates are required.")
        with self._lock:
            data = self._read_data()
            font = next((item for item in data["fonts"] if item["id"] == font_id), None)
            if font is None:
                raise KeyError(font_id)
            for glyph_id, payload in glyph_updates.items():
                if glyph_id not in GLYPH_LOOKUP:
                    raise ValueError(f"Unknown glyph id: {glyph_id}")
                self._validate_cells(glyph_id, payload.get("cells"))
                font["glyphs"][glyph_id] = {"cells": payload["cells"]}
            font["updated_at"] = utc_now()
            self._write_data(data)
        return self.get_font(font_id)

    def export_font(self, font_id):
        font = self.get_font(font_id)
        return {
            "font": {
                "id": font["id"],
                "name": font["name"],
                "description": font["description"],
                "created_at": font["created_at"],
                "updated_at": font["updated_at"],
            },
            "glyphs": font["glyphs"],
            "exported_at": utc_now(),
        }

    def _validate_cells(self, glyph_id, cells):
        if not isinstance(cells, list) or len(cells) != GRID_ROWS:
            raise ValueError(f"Invalid cell rows for {glyph_id}")
        for row in cells:
            if not isinstance(row, list) or len(row) != GRID_COLS:
                raise ValueError(f"Invalid cell columns for {glyph_id}")
            for value in row:
                if value not in (0, 1):
                    raise ValueError(f"Cell values must be 0 or 1 for {glyph_id}")

    def _expand(self, font):
        expanded = {
            "id": font["id"],
            "name": font["name"],
            "description": font["description"],
            "created_at": font["created_at"],
            "updated_at": font["updated_at"],
            "glyphs": [],
            "tabs": TAB_ORDER,
        }
        stored = font.get("glyphs", {})
        for glyph in GLYPH_CATALOG:
            saved = stored.get(glyph["id"], {})
            expanded["glyphs"].append(with_cells(glyph, saved.get("cells")))
        return expanded

    def _summarize(self, font):
        return {
            "id": font["id"],
            "name": font["name"],
            "description": font["description"],
            "created_at": font["created_at"],
            "updated_at": font["updated_at"],
            "customized_glyphs": len(font.get("glyphs", {})),
        }


class FontMakerHandler(BaseHTTPRequestHandler):
    server_version = "FontMaker/0.1"

    @property
    def store(self):
        return self.server.store

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._serve_static("index.html")
            return
        if parsed.path.startswith("/static/"):
            self._serve_static(parsed.path.removeprefix("/static/"))
            return
        if parsed.path == "/api/fonts":
            self._write_json({"fonts": self.store.list_fonts()})
            return
        if parsed.path.startswith("/api/fonts/") and parsed.path.endswith("/export"):
            font_id = parsed.path.split("/")[3]
            self._handle_export(font_id)
            return
        if parsed.path.startswith("/api/fonts/"):
            font_id = parsed.path.split("/")[3]
            self._handle_font_detail(font_id)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/fonts":
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        try:
            payload = self._read_json()
            font = self.store.create_font(payload.get("name", ""), payload.get("description", ""))
            self._write_json(font, status=HTTPStatus.CREATED)
        except ValueError as error:
            self._write_json({"error": str(error)}, status=HTTPStatus.BAD_REQUEST)

    def do_PUT(self):
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/fonts/") or not parsed.path.endswith("/glyphs"):
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        font_id = parsed.path.split("/")[3]
        try:
            payload = self._read_json()
            font = self.store.update_glyphs(font_id, payload.get("glyphs", {}))
            self._write_json(font)
        except KeyError:
            self._write_json({"error": "Font not found."}, status=HTTPStatus.NOT_FOUND)
        except ValueError as error:
            self._write_json({"error": str(error)}, status=HTTPStatus.BAD_REQUEST)

    def log_message(self, format, *args):
        return

    def _handle_font_detail(self, font_id):
        try:
            self._write_json(self.store.get_font(font_id))
        except KeyError:
            self._write_json({"error": "Font not found."}, status=HTTPStatus.NOT_FOUND)

    def _handle_export(self, font_id):
        try:
            payload = self.store.export_font(font_id)
        except KeyError:
            self._write_json({"error": "Font not found."}, status=HTTPStatus.NOT_FOUND)
            return
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        filename = slugify(payload["font"]["name"]) + ".fontmaker.json"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError("Request body must be valid JSON.") from error

    def _write_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, relative_path):
        path = (STATIC_DIR / relative_path).resolve()
        if STATIC_DIR not in path.parents and path != STATIC_DIR:
            self.send_error(HTTPStatus.FORBIDDEN, "Forbidden")
            return
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        content_type = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
        }.get(path.suffix, "application/octet-stream")
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)


def make_server(host="127.0.0.1", port=8000, data_file=None):
    store = FontStore(data_file or os.environ.get("FONTMAKER_DATA", DEFAULT_DATA_FILE))
    server = ThreadingHTTPServer((host, port), FontMakerHandler)
    server.store = store
    return server


def main():
    host = os.environ.get("FONTMAKER_HOST", "127.0.0.1")
    port = int(os.environ.get("FONTMAKER_PORT", "8000"))
    server = make_server(host=host, port=port)
    print(f"FontMaker listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
