"""Review queue client and helpers for scanned products. No Streamlit import, so testable.

The mobile gateway (product-langflow's mobile_api, default port 8003) researches
barcodes the app scanned that aren't in the product store; this reviews them.
"""

from urllib.parse import quote

from . import client

DEFAULT_URL = "http://127.0.0.1:8003"
HINT = "(docker compose up -d --build mobile in product-langflow)"
STATUSES = ["pending", "queued", "researching", "not_found", "error", "approved", "rejected"]
TEXT_FIELDS = [("name", "Name"), ("brand", "Brand"), ("brand_owner", "Brand owner"), ("category", "Category"),
               ("package_size", "Package size"), ("serving_text", "Serving (as printed)"),
               ("image_url", "Image URL")]
NUTRIENTS = [("energy_kcal", "Energy (kcal)"), ("protein_g", "Protein (g)"), ("fat_g", "Fat (g)"),
             ("saturated_fat_g", "Saturated fat (g)"), ("trans_fat_g", "Trans fat (g)"),
             ("carbs_g", "Carbohydrates (g)"), ("sugars_g", "Sugars (g)"), ("added_sugars_g", "Added sugars (g)"),
             ("fiber_g", "Fiber (g)"), ("sodium_mg", "Sodium (mg)"), ("cholesterol_mg", "Cholesterol (mg)")]
SOURCE_NAMES = {"usda": "USDA (live)", "open_food_facts": "Open Food Facts", "web": "Web search", "kroger": "Kroger"}


def _call(url, method, path, payload=None, admin_key=None, session=None, timeout=120):
    headers = {"X-Admin-Key": admin_key} if admin_key else None
    if headers:  # client.call has no headers parameter; use a session that adds them
        session = _HeaderSession(session, headers)
    return client.call(url, method, path, payload, timeout=timeout, session=session, hint=HINT)[0]


class _HeaderSession:
    def __init__(self, inner, headers):
        import requests
        self.inner, self.headers = inner or requests, headers

    def request(self, method, url, json=None, timeout=None):
        return self.inner.request(method, url, json=json, timeout=timeout, headers=self.headers)


def queue(url, status="pending", admin_key=None, session=None):
    path = "/admin/review" + (f"?status={status}" if status else "?status=")
    return _call(url, "GET", path, admin_key=admin_key, session=session)


def item(url, barcode, admin_key=None, session=None):
    return _call(url, "GET", f"/admin/review/{quote(barcode)}", admin_key=admin_key, session=session)


def approve(url, barcode, edits=None, note=None, admin_key=None, session=None):
    return _call(url, "POST", f"/admin/review/{quote(barcode)}/approve", {"edits": edits or None, "note": note},
                 admin_key=admin_key, session=session)


def reject(url, barcode, note=None, admin_key=None, session=None):
    return _call(url, "POST", f"/admin/review/{quote(barcode)}/reject", {"note": note},
                 admin_key=admin_key, session=session)


def research(url, barcode, admin_key=None, session=None):
    return _call(url, "POST", f"/admin/review/{quote(barcode)}/research", admin_key=admin_key, session=session)


# --- display and editing ---------------------------------------------------------------

def label(entry):
    """Queue row label: 'Fairlife — High Quality Protein (811620022118) · 3 scans · medium'."""
    d = entry.get("draft") or {}
    name = " — ".join(v for v in (d.get("brand"), d.get("name")) if v) or "(no name found)"
    scans = entry.get("scan_count") or 0
    parts = [f"{name} ({entry['barcode']})", f"{scans} scan{'s' if scans != 1 else ''}"]
    if entry.get("confidence"):
        parts.append(entry["confidence"])
    return " · ".join(parts)


def field_source(entry, field):
    src = (entry.get("field_sources") or {}).get(field)
    return SOURCE_NAMES.get(src, src) if src else None


def source_rows(entry):
    """One row per source that found the product: name, link, how many fields it supplied."""
    supplied = {}
    for src in (entry.get("field_sources") or {}).values():
        supplied[src] = supplied.get(src, 0) + 1
    return [{"source": SOURCE_NAMES.get(k, k), "link": (v or {}).get("url"), "fields used": supplied.get(k, 0)}
            for k, v in (entry.get("sources") or {}).items() if v]


def edits(original, values):
    """The fields the reviewer changed (``values`` = form values in the same shape as the
    draft); unchanged fields are left out so the server keeps their source."""
    out = {}
    for k, v in values.items():
        if k == "nutrients_100g":
            before = original.get("nutrients_100g") or {}
            changed = {n: x for n, x in v.items() if x != before.get(n)}
            if changed:
                out["nutrients_100g"] = changed
        elif (v or None) != (original.get(k) or None):
            out[k] = v
    return out
