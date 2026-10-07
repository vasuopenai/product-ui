"""Thin HTTP client for the product API. No Streamlit import, so testable."""

import time

import requests

DEFAULT_URL = "http://127.0.0.1:8000"


class ApiError(Exception):
    """A user-facing error message for a failed API call."""


def _detail(resp):
    try:
        body = resp.json()
    except ValueError:
        return (resp.text or "").strip()[:500]
    if isinstance(body, dict) and "detail" in body:
        detail = body["detail"]
        return detail if isinstance(detail, str) else str(detail)
    return str(body)[:500]


def call(base_url, method, path, payload=None, timeout=120, session=None):
    """Call the API and return (json, elapsed_seconds); raise ApiError on any failure."""
    url = base_url.rstrip("/") + path
    http = session or requests
    start = time.perf_counter()
    try:
        resp = http.request(method, url, json=payload, timeout=timeout)
    except requests.exceptions.ConnectionError:
        raise ApiError(f"Cannot reach the API at {base_url}. Is it running? "
                       "(docker compose up -d --build api, or uvicorn off_products.api:app)")
    except requests.exceptions.Timeout:
        raise ApiError(f"The API at {base_url} did not answer within {timeout} s.")
    except requests.exceptions.RequestException as e:
        raise ApiError(f"Request to {url} failed: {e}")
    elapsed = time.perf_counter() - start
    if resp.status_code >= 400:
        detail = _detail(resp) or resp.reason
        raise ApiError(f"API error {resp.status_code} on {method} {path}: {detail}")
    try:
        return resp.json(), elapsed
    except ValueError:
        raise ApiError(f"API returned a non-JSON response on {method} {path}.")


def health(base_url, timeout=5, session=None):
    return call(base_url, "GET", "/health", timeout=timeout, session=session)[0]


def ask(base_url, question, session=None):
    return call(base_url, "POST", "/ask", {"question": question}, session=session)


def search(base_url, spec, session=None):
    return call(base_url, "POST", "/search", spec, session=session)
