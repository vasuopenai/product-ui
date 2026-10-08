"""Whole Foods brand products service client. No Streamlit import, so testable.

The service (product-langflow's wholefoods, default port 8002) lists the products
Whole Foods Market reports to USDA under its own brands. Its product rows use the
same fields as the product API's results, so the UI shows them the same way.
"""

from urllib.parse import urlencode

from . import client

DEFAULT_URL = "http://127.0.0.1:8002"
HINT = "(docker compose up -d --build wholefoods in product-langflow)"
PAGE_SIZE = 50


def _get(url, path, session=None, timeout=60):
    return client.call(url, "GET", path, timeout=timeout, session=session, hint=HINT)[0]


def health(url, session=None):
    return _get(url, "/health", session, timeout=5)


def facets(url, session=None):
    return _get(url, "/facets", session)


def products(url, q=None, category=None, brand=None, page=1, session=None):
    """One page of products: {"total", "offset", "products"}."""
    params = {k: v for k, v in (("q", q), ("category", category), ("brand", brand)) if v}
    params.update(limit=PAGE_SIZE, offset=(max(page, 1) - 1) * PAGE_SIZE)
    return _get(url, "/products?" + urlencode(params), session)


def pages(total):
    return max(1, -(-total // PAGE_SIZE))


def facet_options(items, key):
    """Selectbox options like '365 Everyday Value (1,014)' -> value, with 'All' first."""
    return {"All": None, **{f"{i[key]} ({i['count']:,})": i[key] for i in items}}
