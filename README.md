# minutes-agent

LLM task service for Flipkart Minutes.

## Current focus

The first cut mirrors the knowledge-oriented approach used in `food-agent`, but for Minutes products instead of dishes or restaurants.

Current tasks:

- `dimension_summary` -> `POST /v1/llm/enrich/dimension-summary`
- `purchase_behavior_summary` -> `POST /v1/llm/enrich/purchase-behavior-summary`
- `fetch_product_knowledge` -> `POST /v1/llm/knowledge/fetch-product`
- `product_semantic_paragraph` -> `POST /v1/llm/enrich/product-paragraph`

## Run

```bash
source .venv/bin/activate
pip install -e ../alfred
pip install -r requirements.txt
python app.py --provider openai --model gpt-5.4-mini-2026-03-17
```

To enable both summary tasks, include them in `--tasks` when running `app.py`, or in
`MINUTES_AGENT_TASKS` when using the ASGI app factory. For example:

```bash
python app.py --tasks dimension_summary,purchase_behavior_summary --provider qwen \
  --vllm-url <qwen-openai-compatible-base-url> \
  --model Qwen3.6-35B-A3B
```

## Dimension summary

Dimension summary requests use a list for each dimension's `value`:

```json
{"dimensions": [{"key": "active_or_special_ingredients", "value": ["watermelon", "zinc", "vitamin_c"]}, {"key": "sku_tier", "value": ["premium_branded"]}]}
```

Each prompt item contains its dimension name and selected string or boolean values. When the name
exists in `data/dimension-reference.json`, the service also injects that description and any value
explanations matching the request. Names absent from the reference are sent without extra context.
The reference is intentionally limited to dimensions or values that need clarification.

One structured model call returns sentence groups with the input indices covered by each sentence.
The service verifies that every requested dimension is covered exactly once and joins the sentences
into one paragraph. Invalid coverage or malformed sentences trigger one correction attempt. The
public response remains `{"summary": "..."}`.

The same reference file contains optional `value_explanations` within each dimension
to clarify ambiguous selected values (currently bilona, BLDC and azo-free). Edit these
curated explanations directly in the JSON. The prompt receives descriptions and only
explanations matching the supplied dimension values, rather than a complete value list.

After editing `docs/dimesion-values.md`, regenerate the reference and restart the service to reload
it. Regeneration refreshes only the entries already present in the curated JSON and preserves their
value explanations:

```bash
python scripts/generate_dimension_reference.py
```

## Purchase-behavior summary

The purchase task accepts verticals containing purchased product titles and optional product types:

```json
{
  "verticals": [
    {
      "vertical": "milk",
      "products": [
        {"title": "Amul Toned Milk", "type": "toned"},
        {"title": "Mother Dairy Full Cream Milk", "type": "full cream"}
      ]
    },
    {
      "vertical": "chocolates",
      "products": [
        {"title": "Hershey's Milk Chocolate"},
        {"title": "Cadbury Dairy Milk"}
      ]
    }
  ]
}
```

The output is one category-level paragraph describing the verticals and general product types the
customer purchases. Exact titles, brands and individual SKUs are not repeated. Missing `type` values
are allowed; the model may infer only an obvious general type from the title. Repeated input entries
can support recurring behavior, while single entries are treated only as evidence of that purchase.

The response is:

```json
{"summary": "The customer buys toned and full-cream milk alongside milk chocolate products."}
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
