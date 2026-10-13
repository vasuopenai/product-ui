"""Usage tab helpers in the UI."""

from tests.test_review_ui import HeaderSession
from ui import usage as us

REPORT = {"active": {"1d": 1, "7d": 3, "30d": 4}, "total_installs": 5, "returning_installs": 2,
          "actions_total": {"ask": 7, "scan": 2},
          "daily": [{"day": "2026-10-11", "active": 2, "new": 1, "ask": 3},
                    {"day": "2026-10-12", "active": 1, "scan": 2}],
          "installs": [{"install": "a1b2c3d4", "first_seen": "2026-10-11", "last_seen": "2026-10-12",
                        "days_active": 2, "ask": 3, "scan": 2, "product_view": 0, "store_lookup": 0, "web": 0}],
          "days": 30, "timezone": "UTC"}


def test_headline_and_tables():
    assert us.headline(REPORT)[0] == ("Active today", 1)
    assert us.headline(REPORT)[-1] == ("Came back on another day", 2)
    rows = us.daily_rows(REPORT)
    assert rows[0]["New installs"] == 1 and rows[0]["Questions"] == 3 and rows[0]["Scans"] == 0
    assert rows[1]["New installs"] == 0 and rows[1]["Scans"] == 2
    inst = us.install_rows(REPORT)[0]
    assert (inst["Install"], inst["Days active"], inst["Questions"]) == ("a1b2c3d4", 2, 3)
    assert us.action_totals(REPORT)[:3] == [("Questions", 7), ("Scans", 2), ("Product views", 0)]


def test_empty_report():
    assert us.daily_rows({}) == [] and us.install_rows({}) == []
    assert us.headline({})[3] == ("Installs ever", 0)


def test_report_sends_days_and_admin_key():
    s = HeaderSession(REPORT)
    us.report("http://gw", days=7, admin_key="k", session=s)
    method, url, _, headers = s.calls[0]
    assert (method, url, headers) == ("GET", "http://gw/admin/usage?days=7", {"X-Admin-Key": "k"})
