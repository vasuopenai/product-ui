"""App usage client and helpers. No Streamlit import, so testable.

The mobile gateway (product-langflow's mobile_api/usage.py) counts app actions per day and random
install ID (no names or emails) and reports them at /admin/usage.
"""

from .review import _call

# Action keys from the gateway, in the order shown, with their column labels.
ACTIONS = [("ask", "Questions"), ("scan", "Scans"), ("product_view", "Product views"),
           ("store_lookup", "Store lookups"), ("web", "Web searches")]


def report(url, days=30, admin_key=None, session=None):
    return _call(url, "GET", f"/admin/usage?days={int(days)}", admin_key=admin_key, session=session)


def headline(r):
    """[(label, value)] for the metric row."""
    a = r.get("active") or {}
    return [("Active today", a.get("1d", 0)), ("Active, last 7 days", a.get("7d", 0)),
            ("Active, last 30 days", a.get("30d", 0)), ("Installs ever", r.get("total_installs", 0)),
            ("Came back on another day", r.get("returning_installs", 0))]


def daily_rows(r):
    """One row per day with active and new installs and each action's count (0 when missing)."""
    return [{"day": d["day"], "Active installs": d.get("active", 0), "New installs": d.get("new", 0),
             **{label: d.get(key, 0) for key, label in ACTIONS}} for d in r.get("daily") or []]


def install_rows(r):
    return [{"Install": i["install"], "First seen": i["first_seen"], "Last seen": i["last_seen"],
             "Days active": i["days_active"], **{label: i.get(key, 0) for key, label in ACTIONS}}
            for i in r.get("installs") or []]


def action_totals(r):
    t = r.get("actions_total") or {}
    return [(label, t.get(key, 0)) for key, label in ACTIONS]
