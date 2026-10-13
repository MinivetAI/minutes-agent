# minutes-agent

LLM task service for Flipkart Minutes.

## Current focus

The first cut mirrors the knowledge-oriented approach used in `food-agent`, but for Minutes products instead of dishes or restaurants.

Current tasks:

- `dimension_summary` -> `POST /v1/llm/enrich/dimension-summary`
- `fetch_product_knowledge` -> `POST /v1/llm/knowledge/fetch-product`
- `product_semantic_paragraph` -> `POST /v1/llm/enrich/product-paragraph`

## Run

```bash
source .venv/bin/activate
pip install -e ../alfred
pip install -r requirements.txt
python app.py --provider openai --model gpt-5.4-mini-2026-03-17
```

To enable dimension summaries, include `dimension_summary` in `--tasks` when running
`app.py`, or in `MINUTES_AGENT_TASKS` when using the ASGI app factory. For example:

```bash
python app.py --tasks dimension_summary --provider qwen \
  --vllm-url http://prod.dev.internal/llm/v1 \
  --model Qwen3.6-35B-A3B
```

Dimension summary requests keep the same input format:

```json
{"dimensions": [{"key": "nutritional_claims", "value": "high_protein"}, {"key": "premium_sku"}]}
```

The service adds each matching description from `data/dimension-reference.json` directly beside
that dimension's name and selected value in the LLM request. It separately marks names that have no
reference. One structured model call returns one to four sentence groups with the input indices
covered by each sentence. The service validates that every requested dimension is covered and joins
the sentences into one coherent paragraph, including repeated dimensions. The response remains
`{"summary": "..."}`; internal descriptions and indices are not exposed. Invalid coverage or
empty sentences trigger one correction attempt, then fail rather than return an incomplete summary.
Each prompt item explicitly identifies its `dimension_name` and `selected_value`; related dimensions
may share a sentence while retaining their distinct meanings and values. Requests
accept 1–64 dimensions, with a 4096-token generation budget. Value lists
remain in the Markdown; selected values come from the request.

The same reference file contains optional `value_explanations` within each dimension
to clarify ambiguous selected values (currently bilona, BLDC and azo-free). Edit these
curated explanations directly in the JSON. The prompt receives descriptions and only
explanations matching the supplied dimension and value, rather than a complete value list.

After editing `docs/dimesion-values.md`, regenerate the reference and restart the
service to reload it. Regeneration preserves the curated value explanations:

```bash
python scripts/generate_dimension_reference.py
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
