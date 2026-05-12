# minutes-agent

LLM task service for Flipkart Minutes.

## Current focus

The first cut mirrors the knowledge-oriented approach used in `food-agent`, but for Minutes products instead of dishes or restaurants.

Current tasks:

- `fetch_product_knowledge` -> `POST /v1/llm/knowledge/fetch-product`
- `product_semantic_paragraph` -> `POST /v1/llm/enrich/product-paragraph`

## Run

```bash
source ../minivet/bin/activate
pip install -r requirements.txt
python app.py --provider openai --model gpt-5.4-mini-2026-03-17
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
