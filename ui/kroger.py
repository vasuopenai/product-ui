"""Kroger service client and display helpers. No Streamlit import, so testable.

The Kroger service (product-langflow's kroger_sync, default port 8001) looks
products up by barcode and returns price, sale, aisle, image and stock for the
chosen Kroger store.
"""

from . import client

DEFAULT_URL = "http://127.0.0.1:8001"
HINT = "(docker compose up -d --build kroger in product-langflow)"

# Product categories of the product store, for bulk loads.
CATEGORIES = [
    "cat:snacks", "cat:snack-bars", "cat:chips-pretzels", "cat:popcorn-nuts-seeds", "cat:crackers",
    "cat:cookies", "cat:chocolate", "cat:candy", "cat:other-snacks", "cat:cereal", "cat:yogurt",
    "cat:cheese", "cat:milk", "cat:nut-seed-butters", "cat:breads", "cat:cakes-pastries",
    "cat:ice-cream-frozen-desserts", "cat:meals", "cat:pizza", "cat:soups", "cat:meat-poultry",
    "cat:fish-seafood", "cat:pasta-rice-grains", "cat:sauces-condiments", "cat:dips-salsa",
    "cat:fruit-vegetables", "cat:juice", "cat:soda", "cat:water", "cat:coffee-tea",
    "cat:sports-protein-drinks", "cat:other-drinks", "cat:powders-mixes",
]


def _call(url, method, path, payload=None, timeout=60, session=None):
    return client.call(url, method, path, payload, timeout=timeout, session=session, hint=HINT)[0]


def health(url, session=None):
    return _call(url, "GET", "/health", timeout=5, session=session)


def locations(url, zip_code, session=None):
    return _call(url, "GET", f"/locations?zip={zip_code}", session=session)["locations"]


def choose_store(url, location_id, name=None, session=None):
    return _call(url, "PUT", "/store", {"location_id": location_id, "name": name}, session=session)


def items(url, codes, lookup=True, session=None):
    """{code: item} for the given barcodes, plus the service's lookup stats."""
    return _call(url, "POST", "/items", {"codes": list(codes), "lookup": lookup}, session=session)


def start_run(url, mode, categories=None, session=None):
    return _call(url, "POST", "/runs", {"mode": mode, "categories": categories or None}, session=session)


def latest_run(url, session=None):
    return _call(url, "GET", "/runs/latest", session=session)


def coverage(url, session=None):
    return _call(url, "GET", "/coverage", session=session)


# --- display -------------------------------------------------------------------

def price_text(item):
    """'$3.99 (sale, was $4.49) · Aisle 12' / 'not sold at Kroger' / '' (unknown)."""
    if not item:
        return ""
    if not item.get("sold"):
        return "not sold at Kroger"
    parts = []
    if item.get("price") is not None:
        price = f"${item['price']:.2f}"
        if item.get("on_sale") and item.get("regular_price"):
            price += f" (sale, was ${item['regular_price']:.2f})"
        parts.append(price)
    if item.get("aisle"):
        parts.append(item["aisle"])
    if item.get("stock_level"):
        parts.append(f"stock {item['stock_level'].lower()}")
    return " · ".join(parts) or "sold at Kroger"


def add_kroger_column(rows, products, kroger_items):
    """Add a 'Kroger' column to product table rows (same order as products)."""
    for row, p in zip(rows, products):
        row["Kroger"] = price_text(kroger_items.get(p.get("code")))
    return rows


def only_sold(products, kroger_items):
    return [p for p in products if (kroger_items.get(p.get("code")) or {}).get("sold")]


def status_lines(status):
    """Readable lines for the Kroger tab's status box."""
    lines = [("API keys", "set" if status.get("configured") else "missing — add KROGER_CLIENT_ID / "
              "KROGER_CLIENT_SECRET to product-langflow's .env and restart the kroger service")]
    store = status.get("location_name") or status.get("location_id")
    lines.append(("Store", store or "not chosen"))
    lines.append(("Barcodes looked up", f"{status.get('looked_up', 0):,} ({status.get('sold', 0):,} sold at Kroger)"))
    lines.append(("API calls today", f"{status.get('calls_today', 0):,} of {status.get('daily_budget', 0):,}"))
    run = status.get("last_run")
    if run:
        lines.append(("Last run", f"{run.get('mode')} — {run.get('status')}: {run.get('message')}"))
    return lines
