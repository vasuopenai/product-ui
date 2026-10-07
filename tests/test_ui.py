"""Tests for the UI helpers (no Streamlit, no network)."""

from pathlib import Path

import pytest
import requests

from ui import client, formatting as fmt

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"

SPEC = {
    "semantic_query": "protein bar",
    "categories_any": ["en:protein-bars"],
    "nutrients": [{"nutrient": "protein_g", "basis": "serving", "op": ">=", "value": 20}],
    "ingredient_amounts": [{"ingredient": "en:cocoa", "basis": "percent", "op": ">", "value": 70.0,
                            "declared_only": True}],
    "include_ingredients_all": [],
    "exclude_groups": ["seed_oils"],
    "max_ingredients": None,
    "max_nova_group": None,
    "sort_by": "relevance",
    "limit": 10,
}

PRODUCT = {
    "name": "Choc Bar", "brand": "Acme", "code": "0123", "url": "https://example.org/p/0123",
    "serving_size": "60 g",
    "per_serving": {"energy_kcal": 230.0, "protein_g": 21.5, "sodium_mg": 180},
    "per_100g": {"energy_kcal": 383.3, "protein_g": 35.8, "sugars_g": 3.0},
    "ingredients": "Milk protein, almonds, cocoa",
    "ingredient_count": 3,
    "ingredient_amounts": [{"id": "en:milk-protein", "percent": 40.04, "declared": True},
                           {"id": "en:almond", "percent": None, "declared": False}],
    "groups": {"added_sugars": "maybe"},
    "free_of": ["seed_oils", "artificial_sweeteners"],
    "labels": ["en:gluten-free"],
}


def test_clean_spec_drops_empty_fields():
    cleaned = fmt.clean_spec(SPEC)
    assert "include_ingredients_all" not in cleaned
    assert "max_ingredients" not in cleaned
    assert cleaned["limit"] == 10 and cleaned["semantic_query"] == "protein bar"
    assert fmt.clean_spec(None) == {}


def test_spec_lines_are_readable():
    lines = dict(fmt.spec_lines(SPEC))
    assert lines["Looking for"] == "protein bar"
    assert lines["Category (any of)"] == "en:protein-bars"
    assert lines["Nutrients"] == "protein >= 20 g per serving"
    assert lines["Ingredient amounts"] == "en:cocoa > 70 % (declared on label only)"
    assert lines["Free of"] == "seed_oils"
    assert "Max ingredients" not in lines


@pytest.mark.parametrize("c, text", [
    ({"nutrient": "sodium_mg", "basis": "100g", "op": "<", "value": 140}, "sodium < 140 mg per 100 g"),
    ({"nutrient": "energy_kcal", "basis": "serving", "op": "<=", "value": 200.5},
     "energy <= 200.5 kcal per serving"),
    ({"nutrient": "saturated_fat_g", "basis": "100g", "op": "<", "value": 1.25},
     "saturated_fat < 1.2 g per 100 g"),
])
def test_describe_nutrient(c, text):
    assert fmt.describe_nutrient(c) == text


def test_product_row():
    row = fmt.product_row(PRODUCT)
    assert row["name"] == "Choc Bar" and row["brand"] == "Acme" and row["barcode"] == "0123"
    assert row["protein"] == 21.5 and row["sugars"] is None
    assert row["serving"] == "60 g" and row["ingredients"] == 3
    assert row["free of"] == "seed_oils, artificial_sweeteners"
    assert row["link"] == PRODUCT["url"]


def test_product_row_tolerates_missing_fields():
    row = fmt.product_row({"code": "9"})
    assert row["name"] == "(unnamed)" and row["brand"] == "" and row["link"] is None
    assert row["protein"] is None and row["free of"] == ""
    assert fmt.product_rows(None) == []


def test_nutrition_rows_merge_both_bases():
    rows = {r["nutrient"]: r for r in fmt.nutrition_rows(PRODUCT)}
    assert rows["protein_g"] == {"nutrient": "protein_g", "per serving": "21.5 g", "per 100 g": "35.8 g"}
    assert rows["sugars_g"]["per serving"] == "" and rows["sugars_g"]["per 100 g"] == "3 g"
    assert rows["sodium_mg"]["per serving"] == "180 mg"
    assert "fat_g" not in rows


def test_amount_rows_and_title():
    rows = fmt.amount_rows(PRODUCT)
    assert rows[0] == {"ingredient": "en:milk-protein", "percent": 40.0, "source": "label"}
    assert rows[1]["percent"] is None and rows[1]["source"] == "estimate"
    assert fmt.product_title(PRODUCT) == "Choc Bar — Acme (0123)"
    assert fmt.product_title({"name": "X"}) == "X"


def test_examples_load():
    presets = fmt.load_presets(EXAMPLES)
    assert "dark_chocolate" in presets and presets["dark_chocolate"]["semantic_query"]
    assert fmt.load_questions(EXAMPLES / "questions.txt")
    assert fmt.load_questions(EXAMPLES / "missing.txt") == []


def test_parse_spec():
    assert fmt.parse_spec('{"semantic_query": "x"}') == ({"semantic_query": "x"}, None)
    assert fmt.parse_spec("[1]")[1].startswith("The spec must be")
    assert fmt.parse_spec("{bad")[1].startswith("Invalid JSON")


class FakeResponse:
    def __init__(self, status, body=None, text=""):
        self.status_code, self._body, self.text, self.reason = status, body, text, "Reason"

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


class FakeSession:
    def __init__(self, response=None, exc=None):
        self.response, self.exc, self.calls = response, exc, []

    def request(self, method, url, json=None, timeout=None):
        self.calls.append((method, url, json))
        if self.exc:
            raise self.exc
        return self.response


def test_client_success_and_url_join():
    s = FakeSession(FakeResponse(200, {"products": []}))
    body, elapsed = client.search("http://api:8000/", {"semantic_query": "x"}, session=s)
    assert body == {"products": []} and elapsed >= 0
    assert s.calls == [("POST", "http://api:8000/search", {"semantic_query": "x"})]
    client.ask("http://api:8000", "q?", session=s)
    assert s.calls[-1] == ("POST", "http://api:8000/ask", {"question": "q?"})


def test_client_errors_are_readable():
    down = FakeSession(exc=requests.exceptions.ConnectionError())
    with pytest.raises(client.ApiError, match="Cannot reach the API"):
        client.health("http://127.0.0.1:1", session=down)
    bad = FakeSession(FakeResponse(400, {"detail": "unknown operator =="}))
    with pytest.raises(client.ApiError, match="400.*unknown operator =="):
        client.search("http://x", {}, session=bad)
    crash = FakeSession(FakeResponse(500, None, text="Internal Server Error"))
    with pytest.raises(client.ApiError, match="500.*Internal Server Error"):
        client.search("http://x", {}, session=crash)
