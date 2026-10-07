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

from ui import client, formatting as fmt  # noqa: E402

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

history = st.session_state.setdefault("history", [])


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


def show_products(products):
    if not products:
        st.info("No products returned.")
        return
    st.subheader(f"Products ({len(products)})")
    st.dataframe(
        fmt.product_rows(products),
        hide_index=True,
        column_config={"link": st.column_config.LinkColumn("link", display_text="open")},
    )
    for p in products:
        with st.expander(fmt.product_title(p)):
            cols = st.columns([1, 3]) if p.get("image_url") else [None, st.container()]
            if p.get("image_url"):
                cols[0].image(p["image_url"], width="stretch")
            body = cols[1]
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

ask_tab, search_tab = st.tabs(["Ask", "Search by filters"])

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
