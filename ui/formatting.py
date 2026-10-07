"""Pure formatting helpers for the Streamlit UI (no Streamlit import, so testable).

Everything here works on the JSON returned by the HTTP API and tolerates
missing keys, so the UI keeps working if the data source adds or drops fields.
"""

import json
from pathlib import Path

# Nutrients shown as table columns, in order: (key, column label, unit).
NUTRIENTS = [
    ("energy_kcal", "kcal", ""),
    ("protein_g", "protein", "g"),
    ("fat_g", "fat", "g"),
    ("carbs_g", "carbs", "g"),
    ("sugars_g", "sugars", "g"),
    ("fiber_g", "fiber", "g"),
    ("sodium_mg", "sodium", "mg"),
]
_UNITS = {key: unit for key, _, unit in NUTRIENTS}

_SPEC_LABELS = {
    "semantic_query": "Looking for",
    "categories_any": "Category (any of)",
    "nutrients": "Nutrients",
    "ingredient_amounts": "Ingredient amounts",
    "include_ingredients_all": "Must contain",
    "exclude_ingredients": "Must not contain",
    "first_ingredient_any": "First ingredient (any of)",
    "exclude_groups": "Free of",
    "include_groups": "Contains group",
    "max_ingredients": "Max ingredients",
    "labels_all": "Labels",
    "exclude_allergens": "Without allergens",
    "countries_any": "Countries (any of)",
    "max_nova_group": "Max NOVA group",
    "sort_by": "Sort by",
    "limit": "Limit",
}
_BASIS = {
    "serving": "per serving",
    "100g": "per 100 g",
    "percent": "%",
    "grams_per_100g": "g per 100 g",
    "grams_per_serving": "g per serving",
}


def _empty(v):
    return v is None or v == "" or v == [] or v == {}


def clean_spec(spec):
    """Drop empty fields from a spec dict, keeping the original key order."""
    return {k: v for k, v in (spec or {}).items() if not _empty(v)}


def _num(v):
    """12.0 -> '12', 12.345 -> '12.3'; non-numbers pass through as str."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return str(v)
    return f"{v:.1f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


def describe_nutrient(c):
    """{'nutrient': 'protein_g', 'basis': 'serving', 'op': '>=', 'value': 20}
    -> 'protein >= 20 g per serving'."""
    key = c.get("nutrient", "?")
    name = key.rsplit("_", 1)[0] if key.endswith(("_g", "_mg", "_kcal")) else key
    unit = _UNITS.get(key) or ("mg" if key.endswith("_mg") else "g" if key.endswith("_g") else "")
    if key == "energy_kcal":
        name, unit = "energy", "kcal"
    basis = _BASIS.get(c.get("basis"), c.get("basis", ""))
    return f"{name} {c.get('op', '?')} {_num(c.get('value'))} {unit} {basis}".replace("  ", " ").strip()


def describe_amount(a):
    """{'ingredient': 'en:cocoa', 'basis': 'percent', 'op': '>', 'value': 70}
    -> 'en:cocoa > 70 %'."""
    basis = _BASIS.get(a.get("basis"), a.get("basis", ""))
    text = f"{a.get('ingredient', '?')} {a.get('op', '?')} {_num(a.get('value'))} {basis}".strip()
    return text + (" (declared on label only)" if a.get("declared_only") else "")


def spec_lines(spec):
    """Readable (label, value) pairs for the non-empty fields of a spec."""
    out = []
    for key, value in clean_spec(spec).items():
        label = _SPEC_LABELS.get(key, key.replace("_", " ").capitalize())
        if key == "nutrients":
            value = "; ".join(describe_nutrient(c) for c in value)
        elif key == "ingredient_amounts":
            value = "; ".join(describe_amount(a) for a in value)
        elif isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        elif isinstance(value, dict):
            value = json.dumps(value, ensure_ascii=False)
        else:
            value = _num(value)
        out.append((label, value))
    return out


def fmt_amount(key, value):
    if value is None:
        return ""
    unit = _UNITS.get(key, "")
    return f"{_num(value)} {unit}".strip()


def product_row(p):
    """One flat row for the products table."""
    per_serving = p.get("per_serving") or {}
    row = {
        "name": p.get("name") or "(unnamed)",
        "brand": p.get("brand") or "",
        "barcode": p.get("code") or "",
        "serving": p.get("serving_size") or "",
    }
    for key, label, _ in NUTRIENTS:
        row[label] = per_serving.get(key)
    count = p.get("ingredient_count")
    row["ingredients"] = count if count is not None else None
    row["free of"] = ", ".join(p.get("free_of") or [])
    row["link"] = p.get("url") or None
    return row


def product_rows(products):
    return [product_row(p) for p in products or []]


def nutrition_rows(p):
    """Rows of (nutrient, per serving, per 100 g) for every nutrient either basis has."""
    serv, per100 = p.get("per_serving") or {}, p.get("per_100g") or {}
    known = [k for k, _, _ in NUTRIENTS]
    keys = known + sorted((set(serv) | set(per100)) - set(known))
    return [
        {"nutrient": k, "per serving": fmt_amount(k, serv.get(k)), "per 100 g": fmt_amount(k, per100.get(k))}
        for k in keys if k in serv or k in per100
    ]


def amount_rows(p):
    """Top-level ingredient percentages, marking label-declared vs estimated."""
    rows = []
    for a in p.get("ingredient_amounts") or []:
        pct = a.get("percent")
        rows.append({
            "ingredient": a.get("id", "?"),
            "percent": None if pct is None else round(float(pct), 1),
            "source": "label" if a.get("declared") else "estimate",
        })
    return rows


def product_title(p):
    name = p.get("name") or "(unnamed)"
    brand = p.get("brand")
    code = p.get("code")
    title = f"{name} — {brand}" if brand else name
    return f"{title} ({code})" if code else title


def load_presets(folder):
    """{file stem: spec dict} for every readable *.json in ``folder``."""
    presets = {}
    for path in sorted(Path(folder).glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            presets[path.stem] = data
    return presets


def load_questions(path):
    """Example questions, one per line; missing file -> []."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return []
    return [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]


def parse_spec(text):
    """Parse the JSON editor contents. Returns (spec, error_message)."""
    try:
        spec = json.loads(text)
    except ValueError as e:
        return None, f"Invalid JSON: {e}"
    if not isinstance(spec, dict):
        return None, "The spec must be a JSON object, e.g. {\"semantic_query\": \"dark chocolate\"}"
    return spec, None
