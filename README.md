# product-ui

Web UI for the food product question-answering API
([product-langflow](https://github.com/vasuopenai/product-langflow)). It talks to the
API only over HTTP (`GET /health`, `POST /ask`, `POST /search`), so it works whatever
data source the API is loaded from and can grow into its own app.

- **Sidebar**: API base URL (from `API_URL`, default `http://127.0.0.1:8000`), a health
  indicator with the product count, and the last few questions/searches (click one to
  show it again).
- **Ask**: type a question (or pick one from `examples/questions.txt`). Shows the parsed
  filters, notes about relaxed or unenforced filters, the answer, a products table and a
  details panel per product (ingredients, ingredient amounts, full nutrition, link, image
  when the API returns `image_url`). Each question calls the language model behind the
  API, so it costs a little.
- **Search by filters**: edit a filter spec as JSON (presets in `examples/*.json`) and
  call `/search`. No language model involved.

On Windows use `127.0.0.1`, not `localhost` (localhost tries IPv6 first and can hang).

## Run locally on Windows

1. Start the API from the product-langflow project:

   ```powershell
   cd C:\Users\vasub\food-genei\product-langflow
   docker compose up -d --build api
   ```

2. Set up this project once:

   ```powershell
   cd C:\Users\vasub\food-genei\product-ui
   uv venv --python 3.12 .venv
   uv pip install --python .venv\Scripts\python.exe -r requirements.txt pytest
   ```

3. Run it and open http://127.0.0.1:8501:

   ```powershell
   .venv\Scripts\python -m streamlit run ui/app.py
   ```

   To point it at another API: `$env:API_URL = "http://127.0.0.1:8001"` before running
   (or edit the URL in the sidebar).

## Run with Docker

```powershell
docker compose up -d --build     # open http://127.0.0.1:8501
```

The container reaches the API on the host at `http://host.docker.internal:8000`;
set `API_URL` to use another address.

## Trying it without paid calls

Run the API with the fake embedder and use the **Search by filters** tab; `/search`
then makes no OpenAI calls (relevance order is meaningless, but all hard filters
apply). `/ask` always calls the chat model.

```powershell
cd C:\Users\vasub\food-genei\product-langflow
$env:OFF_EMBEDDER = "fake"
.venv\Scripts\python -m uvicorn off_products.api:app --host 127.0.0.1 --port 8000
```

## Tests

Formatting and HTTP helpers live in `ui/formatting.py` and `ui/client.py` (no Streamlit
import) and are tested in `tests/test_ui.py`:

```powershell
.venv\Scripts\python -m pytest -q tests
```

## Kroger

With product-langflow's Kroger service running (`docker compose up -d --build kroger`,
port 8001; set `KROGER_API_URL` or edit it in the sidebar), results show Kroger
price, sale, aisle and stock for the chosen store, with a "Sold at Kroger only"
toggle. The **Kroger** tab picks the store and runs optional bulk loads/refreshes
by category. Barcodes are looked up on demand and cached by the service.

## Whole Foods

The **Whole Foods** tab lists the ~3,000 products Whole Foods Market reports to USDA
under its own brands (365, Whole Foods Market, Engine 2, ...), from product-langflow's
wholefoods service (`docker compose up -d --build wholefoods`, port 8002; set
`WHOLEFOODS_API_URL` or edit it in the tab). Search name or ingredients, filter by
brand and category, and page through; Kroger prices show here too when that
service is running.

## Review

The **Review** tab works through barcodes scanned in the mobile app that aren't in
the product store (product-langflow's mobile gateway, `docker compose up -d --build mobile`,
port 8003; set `MOBILE_API_URL`, and `MOBILE_ADMIN_KEY` when the gateway requires one).
For each: what USDA, Open Food Facts, Kroger and web search found, which source each
field came from, editable fields and nutrition, and Approve and add / Reject /
Research again. Approved products become searchable immediately.
