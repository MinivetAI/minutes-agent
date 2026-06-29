# minutes-agent

LLM task service for Flipkart Minutes.

## Current focus

The first cut mirrors the knowledge-oriented approach used in `food-agent`, but for Minutes products instead of dishes or restaurants.

Current tasks:

- `fetch_product_knowledge` -> `POST /v1/llm/knowledge/fetch-product`
- `product_semantic_paragraph` -> `POST /v1/llm/enrich/product-paragraph`
- `query_improvement` -> `POST /improve-query`
- `query_parse` -> `POST /parse-query`
- `user_hourly_summary` -> `POST /user/hourly-summary`
- `user_aggregate_summary` -> `POST /user/aggregate-summary`
- `user_category_profile` -> `POST /user/category-profile`
- `user_cross_category_profile` -> `POST /user/cross-category-profile`
- `user_mission_hourly_summary` -> `POST /user/mission-hourly-summary`
- `user_mission_daily_summary` -> `POST /user/mission-daily-summary`
- `user_mission_monthly_summary` -> `POST /user/mission-monthly-summary`
- `user_mission_global_profile` -> `POST /user/mission-global-profile`
- `test_task` -> `POST /test`

Optional tasks (enabled only if the matching instruction constant exists):

- `feed_query_generation` -> `POST /user/feed-queries`

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py --provider qwen --model Qwen/Qwen2.5-14B-Instruct-AWQ
```

To run only the query tasks:

```bash
python app.py --tasks query_improvement,query_parse --provider qwen --model Qwen/Qwen2.5-14B-Instruct-AWQ
```

To run only the mission-profile tasks:

```bash
python app.py \
  --tasks user_mission_hourly_summary,user_mission_daily_summary,user_mission_monthly_summary,user_mission_global_profile \
  --provider qwen \
  --vllm-url http://rtx-5.dev.internal:8000/v1/ \
  --model qwen3-35b \
  --port 8067 \
  --max-concurrent 256
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
- Query improvement and parsing borrow the task shape from `shopsy-agent` and use local Indian and brand context files when available.
- Mission-profile tasks use a compressed hierarchy: raw orders only at hourly
  level, hourly summaries for daily, daily summaries for monthly, and
  compressed hourly/daily/monthly summaries for the global profile.
