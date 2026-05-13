# minutes-agent

LLM task service for Flipkart Minutes.

## Current focus

The first cut mirrors the knowledge-oriented approach used in `food-agent`, but for Minutes products instead of dishes or restaurants.

Current tasks:

- `fetch_product_knowledge` -> `POST /v1/llm/knowledge/fetch-product`
- `product_semantic_paragraph` -> `POST /v1/llm/enrich/product-paragraph`
- `user_hourly_summary` -> `POST /user/hourly-summary`
- `user_aggregate_summary` -> `POST /user/aggregate-summary`
- `user_category_profile` -> `POST /user/category-profile`
- `user_cross_category_profile` -> `POST /user/cross-category-profile`

Optional tasks (enabled only if the matching instruction constant exists):

- `feed_query_generation` -> `POST /user/feed-queries`

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py --provider qwen --model Qwen/Qwen2.5-14B-Instruct-AWQ
```

## Batch sample fetch

```bash
source ../minivet/bin/activate
python scripts/fetch_sample_products.py --limit 10
```

This reads representative products from `/home/aditya/Minivet/minutes/data/minutes_catalog.tsv` and writes JSON outputs under `sample_outputs/`.

## Notes

- The intent model and product understanding notes live in `docs/flipkart-minutes-understanding.md`.
- The current implementation is intentionally small and task-driven.
