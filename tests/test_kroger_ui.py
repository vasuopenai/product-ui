"""Kroger helpers in the UI: service calls and display formatting."""

import pytest
import requests

from tests.test_ui import FakeResponse, FakeSession
from ui import client, kroger as kr

SOLD = {"sold": True, "price": 3.99, "regular_price": 4.49, "on_sale": True, "aisle": "Aisle 12",
        "stock_level": "HIGH"}


def test_price_text():
    assert kr.price_text(SOLD) == "$3.99 (sale, was $4.49) · Aisle 12 · stock high"
    assert kr.price_text({"sold": True, "price": 2.5}) == "$2.50"
    assert kr.price_text({"sold": True}) == "sold at Kroger"
    assert kr.price_text({"sold": False}) == "not sold at Kroger"
    assert kr.price_text(None) == ""


def test_kroger_column_and_sold_only_filter():
    products = [{"code": "1"}, {"code": "2"}, {"code": "3"}]
    items = {"1": SOLD, "2": {"sold": False}}
    rows = kr.add_kroger_column([{}, {}, {}], products, items)
    assert [r["Kroger"] for r in rows] == [kr.price_text(SOLD), "not sold at Kroger", ""]
    assert kr.only_sold(products, items) == [{"code": "1"}]


def test_status_lines():
    lines = dict(kr.status_lines({"configured": False, "looked_up": 1200, "sold": 300,
                                  "calls_today": 24, "daily_budget": 9000,
                                  "last_run": {"mode": "load", "status": "done", "message": "done"}}))
    assert lines["API keys"].startswith("missing") and lines["Store"] == "not chosen"
    assert lines["Barcodes looked up"] == "1,200 (300 sold at Kroger)"
    assert lines["API calls today"] == "24 of 9,000" and lines["Last run"] == "load — done: done"


def test_service_calls():
    s = FakeSession(FakeResponse(200, {"items": {"1": SOLD}, "lookup": {"calls": 1}}))
    assert kr.items("http://k:8001/", ["1"], session=s)["items"]["1"]["sold"]
    assert s.calls[-1] == ("POST", "http://k:8001/items", {"codes": ["1"], "lookup": True})
    kr.start_run("http://k:8001", "load", ["cat:snacks"], session=s)
    assert s.calls[-1] == ("POST", "http://k:8001/runs", {"mode": "load", "categories": ["cat:snacks"]})
    kr.start_run("http://k:8001", "refresh", [], session=s)
    assert s.calls[-1][2] == {"mode": "refresh", "categories": None}  # empty = all products


def test_unreachable_service_names_the_kroger_service():
    down = FakeSession(exc=requests.exceptions.ConnectionError())
    with pytest.raises(client.ApiError, match="docker compose up -d --build kroger"):
        kr.health("http://127.0.0.1:1", session=down)
