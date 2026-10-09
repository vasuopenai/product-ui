"""Catalog gaps client and helpers. No Streamlit import, so testable.

The mobile gateway (product-langflow's mobile_api) reports which Kroger catalog products are
missing from USDA, Open Food Facts and our app (catalog_gaps crawler; docs/CATALOG_GAPS.md),
lists them, and stages a group for review.
"""

from urllib.parse import urlencode

from .review import _call

# The headline numbers, in the order shown.
HEADLINE = [("not_in_usda", "Not in USDA"), ("not_in_off", "Not in Open Food Facts"),
            ("neither", "In neither"), ("not_in_app", "Not in our app")]


def report(url, admin_key=None, session=None):
    return _call(url, "GET", "/admin/catalog/report", admin_key=admin_key, session=session)


def products(url, group=None, category=None, brand=None, q=None, limit=50, offset=0, admin_key=None, session=None):
    params = {k: v for k, v in {"group": group, "category": category, "brand": brand, "q": q,
                                "limit": limit, "offset": offset}.items() if v not in (None, "")}
    return _call(url, "GET", "/admin/catalog/products?" + urlencode(params), admin_key=admin_key, session=session)


def stage(url, group, category=None, brand=None, limit=None, dry_run=False, admin_key=None, session=None):
    return _call(url, "POST", "/admin/catalog/stage",
                 {"group": group, "category": category or None, "brand": brand or None, "limit": limit,
                  "dry_run": dry_run}, admin_key=admin_key, session=session)


def pct(n, total):
    return f"{100 * n / total:.0f}%" if total else "–"


def headline(r):
    """[(label, count, percent of Kroger food products)] for the metric row."""
    total = r.get("kroger_food_products") or 0
    return [(label, r["groups"].get(g, 0), pct(r["groups"].get(g, 0), total)) for g, label in HEADLINE]


def matrix_rows(r):
    m = r.get("usda_x_off") or {}
    return [{"": "In USDA", "In Open Food Facts": m.get("usda_yes__off_yes", 0),
             "Not in Open Food Facts": m.get("usda_yes__off_no", 0)},
            {"": "Not in USDA", "In Open Food Facts": m.get("usda_no__off_yes", 0),
             "Not in Open Food Facts": m.get("usda_no__off_no", 0)}]


def group_options(r):
    """{label shown in the picker: group key}, with counts; the first option is every product."""
    labels = r.get("group_labels") or {}
    out = {f"All Kroger food products ({r.get('kroger_food_products', 0):,})": None}
    for g, label in labels.items():
        out[f"{label} ({r['groups'].get(g, 0):,})"] = g
    return out


def missing_refs(r):
    return [name for name in ("usda", "off") if name not in (r.get("refs") or {})]


def _mark(v):
    return "✓" if v else "✗"


def table_rows(items):
    return [{"photo": i.get("image_url"), "barcode": i["barcode"], "brand": i.get("brand"), "name": i.get("name"),
             "size": i.get("size"), "Kroger category": i.get("category"), "USDA": _mark(i["in_usda"]),
             "OFF": _mark(i["in_off"]), "OFF (US)": _mark(i["in_off_us"]), "In app": _mark(i["in_app"]),
             "Kroger info": i.get("kroger_info") or "", "review": i.get("review_status") or "",
             "ingredients (Kroger)": i.get("ingredients") or ""} for i in items]
