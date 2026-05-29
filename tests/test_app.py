import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

from app import make_server


class FontMakerServerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_file = Path(self.temp_dir.name) / "fonts.json"
        self.server = make_server(port=0, data_file=self.data_file)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp_dir.cleanup()

    def request_json(self, path, method="GET", body=None):
        data = None
        headers = {}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(f"{self.base_url}{path}", data=data, headers=headers, method=method)
        with urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return response, payload

    def test_can_create_and_list_fonts(self):
        _, initial = self.request_json("/api/fonts")
        self.assertEqual(initial["fonts"], [])

        response, created = self.request_json(
            "/api/fonts",
            method="POST",
            body={"name": "Vazir Studio", "description": "Persian test font"},
        )
        self.assertEqual(response.status, 201)
        self.assertEqual(created["name"], "Vazir Studio")
        self.assertGreater(len(created["glyphs"]), 150)

        _, listed = self.request_json("/api/fonts")
        self.assertEqual(len(listed["fonts"]), 1)
        self.assertEqual(listed["fonts"][0]["customized_glyphs"], 0)

    def test_can_save_glyphs_and_export(self):
        _, created = self.request_json("/api/fonts", method="POST", body={"name": "Exportable"})
        glyph_id = "fa-0628-isolated"
        cells = [[0 for _ in range(16)] for _ in range(16)]
        cells[0][0] = 1
        cells[1][1] = 1

        _, updated = self.request_json(
            f"/api/fonts/{created['id']}/glyphs",
            method="PUT",
            body={"glyphs": {glyph_id: {"cells": cells}}},
        )
        glyph = next(item for item in updated["glyphs"] if item["id"] == glyph_id)
        self.assertEqual(glyph["cells"][0][0], 1)
        self.assertEqual(glyph["cells"][1][1], 1)

        request = Request(f"{self.base_url}/api/fonts/{created['id']}/export")
        with urlopen(request) as response:
            exported = json.loads(response.read().decode("utf-8"))
            self.assertIn("attachment;", response.headers["Content-Disposition"])
            self.assertEqual(exported["font"]["name"], "Exportable")
            exported_glyph = next(item for item in exported["glyphs"] if item["id"] == glyph_id)
            self.assertEqual(exported_glyph["cells"][0][0], 1)


if __name__ == "__main__":
    unittest.main()
