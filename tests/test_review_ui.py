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


def test_bulk_payload_and_sample_rows():
    s = HeaderSession({"matching": 2, "sample": []})
    rv.bulk("http://gw", found_via="kroger_catalog", category="Snacks", limit=500, admin_key="k", session=s)
    method, url, payload, headers = s.calls[0]
    assert method == "POST" and url == "http://gw/admin/review/bulk" and headers == {"X-Admin-Key": "k"}
    assert payload["dry_run"] is True and payload["limit"] == 500 and payload["category"] == "Snacks"
    assert rv.SOURCES["Phone scans"] == "scan" and rv.SOURCES["Any"] is None
    row = rv.sample_rows([{"barcode": "1", "name": "Almond Butter", "energy_kcal": 594, "protein_g": 21.9,
                           "sodium_mg": None}])[0]
    assert (row["kcal /100g"], row["protein /100g"], row["sodium /100g"]) == ("594", "21.9 g", "")
