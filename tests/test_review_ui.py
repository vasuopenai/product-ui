"""Review helpers in the UI."""

from tests.test_ui import FakeResponse
from ui import review as rv


class HeaderSession:
    def __init__(self, body):
        self.body, self.calls = body, []

    def request(self, method, url, json=None, timeout=None, headers=None):
        self.calls.append((method, url, json, headers))
        return FakeResponse(200, self.body)


ENTRY = {"barcode": "811620022118", "scan_count": 3, "confidence": "medium",
         "draft": {"name": "High Quality Protein", "brand": "Fairlife",
                   "nutrients_100g": {"protein_g": 8.82, "sugars_g": 0.59}},
         "field_sources": {"name": "open_food_facts", "brand": "open_food_facts",
                           "nutrients_100g.protein_g": "web"},
         "sources": {"open_food_facts": {"url": "https://off/x"}, "web": {"url": "https://fairlife.com"}}}


def test_label_and_sources():
    assert rv.label(ENTRY) == "Fairlife — High Quality Protein (811620022118) · 3 scans · medium"
    assert rv.field_source(ENTRY, "name") == "Open Food Facts"
    assert rv.field_source(ENTRY, "nutrients_100g.protein_g") == "Web search"
    rows = {r["source"]: r for r in rv.source_rows(ENTRY)}
    assert rows["Open Food Facts"]["fields used"] == 2 and rows["Web search"]["link"] == "https://fairlife.com"


def test_edits_only_include_changes():
    values = {"name": "Protein Shake, Chocolate", "brand": "Fairlife", "category": "",
              "nutrients_100g": {"protein_g": 8.82, "sugars_g": 0.6, "fiber_g": None}}
    assert rv.edits(ENTRY["draft"], values) == {"name": "Protein Shake, Chocolate",
                                                "nutrients_100g": {"sugars_g": 0.6}}


def test_admin_key_header_and_paths():
    s = HeaderSession({"status": "approved", "product": {}})
    rv.approve("http://m:8003/", "811620022118", {"name": "x"}, "ok", admin_key="k", session=s)
    method, url, body, headers = s.calls[-1]
    assert (method, url) == ("POST", "http://m:8003/admin/review/811620022118/approve")
    assert body == {"edits": {"name": "x"}, "note": "ok"} and headers == {"X-Admin-Key": "k"}
