"""Catalog gaps helpers in the UI."""

from tests.test_review_ui import HeaderSession
from ui import catalog as cg

REPORT = {"kroger_food_products": 111, "refs": {"usda": {"rows": 441383, "built_at": "2026-10-09T15:00"}},
          "groups": {"not_in_usda": 41, "not_in_off": 2, "neither": 2, "not_in_app": 46, "not_in_off_us": 4},
          "group_labels": {"not_in_usda": "Kroger products not in the USDA database",
                           "neither": "in neither USDA nor Open Food Facts"},
          "usda_x_off": {"usda_yes__off_yes": 70, "usda_no__off_yes": 39, "usda_no__off_no": 2}}


def test_headline_matrix_and_group_options():
    assert cg.headline(REPORT)[0] == ("Not in USDA", 41, "37%")
    assert cg.matrix_rows(REPORT)[1] == {"": "Not in USDA", "In Open Food Facts": 39, "Not in Open Food Facts": 2}
    opts = cg.group_options(REPORT)
    assert list(opts.values()) == [None, "not_in_usda", "neither"]
    assert "Kroger products not in the USDA database (41)" in opts
    assert cg.missing_refs(REPORT) == ["off"]
    assert cg.pct(1, 0) == "–"


def test_table_rows_mark_membership():
    row = cg.table_rows([{"barcode": "36000291452", "brand": "B", "name": "New Chips", "in_usda": False,
                          "in_off": True, "in_off_us": False, "in_app": False, "review_status": "queued"}])[0]
    assert (row["USDA"], row["OFF"], row["In app"], row["review"]) == ("✗", "✓", "✗", "queued")
    assert row["Kroger info"] == ""


def test_calls_send_filters_and_admin_key():
    s = HeaderSession({"total": 0, "items": []})
    cg.products("http://gw", "not_in_usda", "Dairy", None, "milk", limit=50, offset=50, admin_key="k", session=s)
    method, url, _, headers = s.calls[0]
    assert method == "GET" and headers == {"X-Admin-Key": "k"}
    assert url == "http://gw/admin/catalog/products?group=not_in_usda&category=Dairy&q=milk&limit=50&offset=50"
    cg.stage("http://gw", "neither", limit=10, dry_run=True, admin_key="k", session=s)
    assert s.calls[1][2] == {"group": "neither", "category": None, "brand": None, "limit": 10, "dry_run": True}
