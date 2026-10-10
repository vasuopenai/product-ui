"""Whole Foods helpers in the UI."""

from tests.test_ui import FakeResponse, FakeSession
from ui import wholefoods as wf


def test_products_query_and_paging():
    s = FakeSession(FakeResponse(200, {"total": 120, "offset": 50, "products": []}))
    wf.products("http://w:8002/", q="almond butter", category="cat:snacks", brand=None, page=2, session=s)
    method, url, _ = s.calls[-1]
    assert method == "GET" and url == ("http://w:8002/products?q=almond+butter&category=cat%3Asnacks"
                                       "&limit=50&offset=50")
    assert wf.pages(120) == 3 and wf.pages(0) == 1 and wf.pages(50) == 1


def test_facet_options():
    opts = wf.facet_options([{"brand": "365 Everyday Value", "count": 1014}], "brand")
    assert opts == {"All": None, "365 Everyday Value (1,014)": "365 Everyday Value"}
