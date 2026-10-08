"""Streamlit UI for trying the product API.

Run: python -m streamlit run ui/app.py
Env: API_URL (default http://127.0.0.1:8000).

Only talks to the HTTP API (/health, /ask, /search); no database or loader code.
"""

import json
import os
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui import client, formatting as fmt, kroger as kr, review as rv, wholefoods as wf  # noqa: E402

EXAMPLES = Path(os.getenv("EXAMPLES_DIR", ROOT / "examples"))
HISTORY_SIZE = 8

st.set_page_config(page_title="Food product Q&A", layout="wide")


# --- sidebar ---------------------------------------------------------------

@st.cache_data(ttl=10, show_spinner=False)
def check_health(url):
    try:
        return client.health(url), None
    except client.ApiError as e:
        return None, str(e)


with st.sidebar:
    st.header("API")
    api_url = st.text_input("Base URL", value=os.getenv("API_URL", client.DEFAULT_URL)).strip()
    if st.button("Re-check health"):
        check_health.clear()
    status, error = check_health(api_url)
    if error:
        st.error(error)
    else:
        n = status.get("products")
        st.success(f"Healthy — {n:,} products" if isinstance(n, int) else "Healthy")
    st.caption("Use 127.0.0.1 rather than localhost on Windows.")


@st.cache_data(ttl=10, show_spinner=False)
def kroger_status(url):
    try:
        return kr.health(url), None
    except client.ApiError as e:
        return None, str(e)


with st.sidebar:
    st.header("Kroger")
    kroger_url = st.text_input("Kroger service URL", value=os.getenv("KROGER_API_URL", kr.DEFAULT_URL)).strip()
    kstatus, kerror = kroger_status(kroger_url)
    if kerror:
        st.caption("Kroger service not reachable — Kroger prices are hidden.")
    elif not kstatus.get("configured"):
        st.warning("Kroger API keys not set (see the Kroger tab).")
    elif not kstatus.get("location_id"):
        st.info("Choose a Kroger store in the Kroger tab.")
    else:
        st.success(f"Store: {kstatus.get('location_name')}")
    kroger_ready = bool(kstatus and kstatus.get("location_id"))
    kroger_live = bool(kroger_ready and kstatus.get("configured"))

history = st.session_state.setdefault("history", [])
kroger_cache = st.session_state.setdefault("kroger_items", {})  # barcode -> Kroger item


def remember(kind, label, result, elapsed, spec=None):
    item = {"kind": kind, "label": label[:60], "result": result, "elapsed": elapsed, "spec": spec}
    history.append(item)
    del history[:-HISTORY_SIZE]
    st.session_state["shown"] = item


# --- rendering ---------------------------------------------------------------

def show_spec(spec):
    lines = fmt.spec_lines(spec)
    if not lines:
        st.caption("No filters.")
        return
    st.markdown("\n".join(f"- **{label}:** {value}" for label, value in lines))
    with st.expander("Raw spec JSON"):
        st.json(fmt.clean_spec(spec))


def kroger_items_for(products):
    """Kroger info for the shown products: from this session's cache, else the
    service (which looks unknown barcodes up live when keys and a store are set)."""
    if not kroger_ready:
        return {}
    codes = [p["code"] for p in products if p.get("code")]
    missing = [c for c in codes if c not in kroger_cache]
    if missing:
        try:
            with st.spinner("Checking Kroger…"):
                found = kr.items(kroger_url, missing, lookup=kroger_live)
            kroger_cache.update(found.get("items", {}))
            if found.get("lookup", {}).get("budget_reached"):
                st.caption("Kroger daily call budget reached; showing cached Kroger data only.")
            if found.get("lookup", {}).get("error"):
                st.caption(f"Kroger lookup failed: {found['lookup']['error']}")
        except client.ApiError as e:
            st.caption(f"Kroger info unavailable: {e}")
    return {c: kroger_cache[c] for c in codes if c in kroger_cache}


def show_products(products, key="results"):
    if not products:
        st.info("No products returned.")
        return
    kroger_items = kroger_items_for(products)
    if kroger_items and st.toggle("Sold at Kroger only", key=f"kroger-only-{key}"):
        products = kr.only_sold(products, kroger_items)
        if not products:
            st.info("None of these products are sold at the chosen Kroger store.")
            return
    st.subheader(f"Products ({len(products)})")
    rows = fmt.product_rows(products)
    if kroger_items:
        rows = kr.add_kroger_column(rows, products, kroger_items)
    st.dataframe(
        rows,
        hide_index=True,
        column_config={"link": st.column_config.LinkColumn("link", display_text="open")},
    )
    for p in products:
        kitem = kroger_items.get(p.get("code")) or {}
        image = p.get("image_url") or (kitem.get("image_url") if kitem.get("sold") else None)
        with st.expander(fmt.product_title(p)):
            cols = st.columns([1, 3]) if image else [None, st.container()]
            if image:
                cols[0].image(image, width="stretch")
            body = cols[1]
            if kitem:
                text = kr.price_text(kitem)
                as_of = (kitem.get("as_of") or "")[:10]
                body.markdown(f"**Kroger:** {text}" + (f" _(as of {as_of})_" if as_of else ""))
            meta = []
            if p.get("serving_size"):
                meta.append(f"**Serving:** {p['serving_size']}")
            if p.get("ingredient_count") is not None:
                meta.append(f"**Ingredients:** {p['ingredient_count']}")
            if p.get("url"):
                meta.append(f"[Product page]({p['url']})")
            if meta:
                body.markdown(" · ".join(meta))
            body.markdown("**Ingredients**")
            body.write(p.get("ingredients") or "_not available_")
            amounts = fmt.amount_rows(p)
            if amounts:
                body.markdown("**Ingredient amounts**")
                body.dataframe(amounts, hide_index=True)
            nutrition = fmt.nutrition_rows(p)
            body.markdown("**Nutrition**")
            if nutrition:
                body.dataframe(nutrition, hide_index=True)
            else:
                body.write("_not available_")
            if p.get("free_of"):
                body.markdown("**Free of:** " + ", ".join(p["free_of"]))
            if p.get("groups"):
                body.markdown("**Contains groups:** " + ", ".join(f"{g} ({s})" for g, s in p["groups"].items()))
            if p.get("labels"):
                body.markdown("**Labels:** " + ", ".join(p["labels"]))
            body.markdown("**Raw JSON**")
            body.json(p, expanded=False)


def show_result(item):
    result, elapsed = item["result"], item["elapsed"]
    st.caption(f"{item['kind']} · {elapsed:.2f} s")
    if item["kind"] == "ask":
        st.markdown(f"### {result.get('question', item['label'])}")
        st.markdown("**Parsed filters**")
        show_spec(result.get("spec") or {})
        for note in result.get("notes") or []:
            st.warning(note)
        st.markdown("**Answer**")
        st.markdown(result.get("answer") or "_No answer returned._")
    else:
        st.markdown("**Filters sent**")
        show_spec(item.get("spec") or {})
    show_products(result.get("products") or [])


# --- tabs ---------------------------------------------------------------------

ask_tab, search_tab, wf_tab, kroger_tab, review_tab = st.tabs(
    ["Ask", "Search by filters", "Whole Foods", "Kroger", "Review"])

with ask_tab:
    questions = fmt.load_questions(EXAMPLES / "questions.txt")
    example = st.selectbox("Example questions", ["(type your own)"] + questions)
    with st.form("ask"):
        question = st.text_area(
            "Question", value="" if example == "(type your own)" else example, height=80,
            placeholder="e.g. protein bar with at least 20 g protein and no seed oils")
        submitted = st.form_submit_button("Ask", type="primary")
    st.caption("Each question calls the language model behind the API (it costs a little).")
    if submitted:
        if not question.strip():
            st.warning("Type a question first.")
        else:
            with st.spinner("Asking…"):
                try:
                    result, elapsed = client.ask(api_url, question.strip())
                    remember("ask", question.strip(), result, elapsed)
                except client.ApiError as e:
                    st.error(str(e))

with search_tab:
    presets = fmt.load_presets(EXAMPLES)
    names = list(presets) or ["(none)"]
    preset = st.selectbox("Preset", names)
    default = json.dumps(presets.get(preset, {"semantic_query": "dark chocolate", "limit": 10}), indent=2)
    with st.form("search"):
        # Keyed by preset so switching presets reloads the editor contents.
        text = st.text_area("QuerySpec JSON", value=default, height=260, key=f"spec-{preset}")
        searched = st.form_submit_button("Search", type="primary")
    if searched:
        spec, err = fmt.parse_spec(text)
        if err:
            st.error(err)
        else:
            with st.spinner("Searching…"):
                try:
                    result, elapsed = client.search(api_url, spec)
                    label = "search: " + (spec.get("semantic_query") or preset)
                    remember("search", label, result, elapsed, spec)
                except client.ApiError as e:
                    st.error(str(e))


@st.cache_data(ttl=300, show_spinner=False)
def wf_facets(url):
    return wf.facets(url)


@st.cache_data(ttl=60, show_spinner=False)
def wf_page(url, q, category, brand, page):
    return wf.products(url, q, category, brand, page)


with wf_tab:
    st.markdown("Products Whole Foods Market reports to USDA under its own brands (365, Whole Foods "
                "Market, Engine 2, Whole Catch, ...). National brands sold at Whole Foods aren't included.")
    wf_url = st.text_input("Whole Foods service URL", value=os.getenv("WHOLEFOODS_API_URL", wf.DEFAULT_URL),
                           key="wf-url").strip()
    try:
        options = wf_facets(wf_url)
    except client.ApiError as e:
        st.error(str(e))
        options = None
    if options:
        c1, c2, c3 = st.columns([2, 1, 1])
        q = c1.text_input("Search name or ingredients", key="wf-q").strip()
        brands = wf.facet_options(options["brands"], "brand")
        cats = wf.facet_options(options["categories"], "category")
        brand = brands[c2.selectbox("Brand", list(brands), key="wf-brand")]
        category = cats[c3.selectbox("Category", list(cats), key="wf-cat")]
        filters = (q, category, brand)
        if st.session_state.get("wf-filters") != filters:  # new filters start at page 1
            st.session_state["wf-filters"], st.session_state["wf-page"] = filters, 1
        try:
            result = wf_page(wf_url, q or None, category, brand, st.session_state["wf-page"])
        except client.ApiError as e:
            st.error(str(e))
            result = None
        if result:
            n_pages = wf.pages(result["total"])
            nav = st.columns([1, 1, 4])
            if nav[0].button("Previous", disabled=st.session_state["wf-page"] <= 1, key="wf-prev"):
                st.session_state["wf-page"] -= 1
                st.rerun()
            if nav[1].button("Next", disabled=st.session_state["wf-page"] >= n_pages, key="wf-next"):
                st.session_state["wf-page"] += 1
                st.rerun()
            nav[2].caption(f"{result['total']:,} products · page {st.session_state['wf-page']} of {n_pages}")
            show_products(result["products"], key="wf")


def _review_number(value):
    return None if value in (None, "") else float(value)


with review_tab:
    st.markdown("Barcodes scanned in the app that aren't in the product store yet. Each was researched "
                "(USDA live, Open Food Facts, Kroger, web search); approve to add it to the store, "
                "where it becomes searchable.")
    c1, c2 = st.columns([3, 1])
    rv_url = c1.text_input("Mobile gateway URL", value=os.getenv("MOBILE_API_URL", rv.DEFAULT_URL),
                           key="rv-url").strip()
    rv_key = c2.text_input("Admin key", value=os.getenv("MOBILE_ADMIN_KEY", ""), type="password",
                           key="rv-key").strip() or None
    status = st.selectbox("Status", rv.STATUSES, key="rv-status")
    try:
        q = rv.queue(rv_url, status, rv_key)
    except client.ApiError as e:
        st.error(str(e))
        q = None
    if q is not None:
        counts = q.get("counts") or {}
        st.caption(" · ".join(f"{k}: {v}" for k, v in sorted(counts.items())) or "Queue is empty.")
        entries = q.get("items") or []
        if not entries:
            st.info(f"No {status} products.")
        else:
            labels = {rv.label(e): e["barcode"] for e in entries}
            barcode = labels[st.selectbox("Product", list(labels), key="rv-pick")]
            try:
                entry = rv.item(rv_url, barcode, rv_key)
            except client.ApiError as e:
                st.error(str(e))
                entry = None
            if entry:
                draft = entry.get("draft") or {}
                st.markdown(f"**Barcode** {entry['barcode']} · **status** {entry['status']} · "
                            f"**confidence** {entry.get('confidence') or '—'} · **scans** {entry['scan_count']}")
                if entry.get("error"):
                    st.warning(f"Research problems: {entry['error']}")
                left, right = st.columns([1, 2])
                if draft.get("image_url"):
                    left.image(draft["image_url"], width="stretch")
                rows = rv.source_rows(entry)
                if rows:
                    right.markdown("**Sources**")
                    right.dataframe(rows, hide_index=True,
                                    column_config={"link": st.column_config.LinkColumn("link", display_text="open")})
                web = (entry.get("sources") or {}).get("web") or {}
                evidence = (web.get("raw") or {}).get("evidence")
                if evidence:
                    right.caption("Web evidence: " + evidence)

                with st.form(f"rv-form-{barcode}"):
                    values = {}
                    cols = st.columns(2)
                    for i, (field, title) in enumerate(rv.TEXT_FIELDS):
                        src = rv.field_source(entry, field)
                        values[field] = cols[i % 2].text_input(
                            title + (f" · {src}" if src else ""), value=draft.get(field) or "",
                            key=f"rv-{barcode}-{field}")
                    src = rv.field_source(entry, "ingredients")
                    values["ingredients"] = st.text_area("Ingredients" + (f" · {src}" if src else ""),
                                                         value=draft.get("ingredients") or "", height=110,
                                                         key=f"rv-{barcode}-ingredients")
                    s1, s2 = st.columns(2)
                    serving = draft.get("serving_size_g")
                    values["serving_size_g"] = _review_number(s1.text_input(
                        "Serving size", value="" if serving is None else f"{serving:g}",
                        key=f"rv-{barcode}-serving"))
                    units = ["g", "ml"]
                    unit = draft.get("serving_unit") if draft.get("serving_unit") in units else "g"
                    values["serving_unit"] = s2.selectbox("Serving unit", units, index=units.index(unit),
                                                          key=f"rv-{barcode}-unit")
                    st.markdown("**Nutrition per 100 g / 100 ml**")
                    nut = draft.get("nutrients_100g") or {}
                    values["nutrients_100g"] = {}
                    ncols = st.columns(4)
                    for i, (n, title) in enumerate(rv.NUTRIENTS):
                        src = rv.field_source(entry, f"nutrients_100g.{n}")
                        raw = ncols[i % 4].text_input(title, value="" if nut.get(n) is None else f"{nut[n]:g}",
                                                      help=f"from {src}" if src else None,
                                                      key=f"rv-{barcode}-{n}")
                        values["nutrients_100g"][n] = _review_number(raw)
                    note = st.text_input("Review note (optional)", key=f"rv-{barcode}-note")
                    b1, b2, b3 = st.columns(3)
                    do_approve = b1.form_submit_button("Approve and add", type="primary", width="stretch",
                                                       disabled=entry["status"] in ("approved", "researching"))
                    do_reject = b2.form_submit_button("Reject", width="stretch",
                                                      disabled=entry["status"] == "rejected")
                    do_research = b3.form_submit_button("Research again", width="stretch")
                try:
                    if do_approve:
                        done = rv.approve(rv_url, barcode, rv.edits(draft, values), note or None, rv_key)
                        product = done["product"]
                        st.success(f"Added to the product store: {product['name']} ({product['code']})")
                    elif do_reject:
                        rv.reject(rv_url, barcode, note or None, rv_key)
                        st.success("Rejected.")
                    elif do_research:
                        rv.research(rv_url, barcode, rv_key)
                        st.info("Researching again - pick status 'researching', or come back in a minute.")
                except (client.ApiError, ValueError) as e:
                    st.error(str(e))

                with st.expander("Scans"):
                    st.dataframe(entry.get("events") or [], hide_index=True)
                with st.expander("Raw source answers"):
                    st.json({k: (v or {}).get("raw") for k, v in (entry.get("sources") or {}).items()},
                            expanded=False)


def _refresh_kroger():
    kroger_status.clear()
    kroger_cache.clear()


@st.fragment(run_every="5s")
def kroger_run_progress():
    """Polls the latest run while one is in progress."""
    try:
        run = kr.latest_run(kroger_url)
    except client.ApiError as e:
        st.error(str(e))
        return
    if not run:
        st.caption("No load has been run yet.")
        return
    stats = run.get("stats") or {}
    text = f"**{run['mode']}** — {run['status']}: {run.get('message') or ''}"
    (st.info if run["status"] == "running" else st.success if run["status"] == "done" else st.warning)(text)
    if stats:
        st.caption(" · ".join(f"{k.replace('_', ' ')}: {v:,}" if isinstance(v, int) else f"{k}: {v}"
                              for k, v in stats.items()))


with kroger_tab:
    if kerror:
        st.error(kerror)
        st.markdown("Start it from product-langflow: `docker compose up -d --build kroger`")
    else:
        st.markdown("Kroger price, aisle and availability for the products shown, looked up **by barcode** "
                    "for one Kroger store. Lookups happen on demand when results are shown; the load "
                    "below is optional and pre-fills whole categories.")
        st.markdown("\n".join(f"- **{k}:** {v}" for k, v in kr.status_lines(kstatus)))
        st.button("Refresh status", on_click=_refresh_kroger)

        st.subheader("1. Store")
        if not kstatus.get("configured"):
            st.info("Add `KROGER_CLIENT_ID` and `KROGER_CLIENT_SECRET` (free at developer.kroger.com, "
                    "Products scope) to product-langflow's `.env`, then "
                    "`docker compose up -d --build kroger`.")
        else:
            zip_code = st.text_input("ZIP code", max_chars=10, key="kroger-zip")
            if st.button("Find stores") and zip_code.strip():
                try:
                    st.session_state["kroger_locations"] = kr.locations(kroger_url, zip_code.strip())
                except client.ApiError as e:
                    st.error(str(e))
            locs = st.session_state.get("kroger_locations") or []
            if locs:
                labels = {f"{l['name']} — {l['address']} ({l['location_id']})": l for l in locs}
                choice = st.selectbox("Store", list(labels))
                if st.button("Use this store", type="primary"):
                    loc = labels[choice]
                    kr.choose_store(kroger_url, loc["location_id"], f"{loc['name']}, {loc['address']}")
                    _refresh_kroger()
                    st.rerun()

        st.subheader("2. Load (optional) and refresh")
        everything = st.checkbox("All products (about 425k barcodes, ~8,500 API calls over one or more days)")
        cats = [] if everything else st.multiselect("Categories", kr.CATEGORIES, default=["cat:snacks"])
        ready = kstatus.get("configured") and kstatus.get("location_id")
        c1, c2 = st.columns(2)
        for col, mode, label, help_text in (
                (c1, "load", "Load", "Look up barcodes not checked yet (resumes after the daily limit)."),
                (c2, "refresh", "Refresh prices", "Look up every barcode in scope again.")):
            if col.button(label, disabled=not ready or (not everything and not cats), help=help_text,
                          width="stretch"):
                try:
                    kr.start_run(kroger_url, mode, None if everything else cats)
                    _refresh_kroger()
                except client.ApiError as e:
                    st.error(str(e))
        kroger_run_progress()

        st.subheader("Coverage")
        try:
            cov = kr.coverage(kroger_url)
            st.caption(f"{cov['looked_up']:,} barcodes looked up, {cov['sold']:,} sold at the chosen store")
            if cov["by_category"]:
                st.dataframe(cov["by_category"], hide_index=True)
        except client.ApiError as e:
            st.caption(str(e))



# Rendered last so it includes the call made in this run; buttons use callbacks
# so a click takes effect before the result area is drawn on the next run.
def _show(item):
    st.session_state["shown"] = item


def _clear():
    history.clear()
    st.session_state.pop("shown", None)


with st.sidebar:
    st.header("History")
    if not history:
        st.caption("No questions yet.")
    for i, item in enumerate(reversed(history)):
        st.button(item["label"], key=f"hist-{len(history) - i}", width="stretch",
                  on_click=_show, args=(item,))
    if history:
        st.button("Clear history", on_click=_clear)

shown = st.session_state.get("shown")
if shown:
    st.divider()
    show_result(shown)
