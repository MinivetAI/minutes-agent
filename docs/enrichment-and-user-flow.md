# Minutes Enrichment and User-Profile Tasks

This document describes the LLM tasks owned by `minutes-agent` for semantic
product enrichment, semantic mission enrichment, and user-profile generation.
The recommendation service or offline Spark pipeline supplies evidence and
consumes these typed outputs; it does not own duplicate prompts.

## Ownership

| Domain | Task | Endpoint |
| --- | --- | --- |
| Product | `fetch_product_knowledge` | `POST /v1/llm/knowledge/fetch-product` |
| Product | `product_semantic_paragraph` | `POST /v1/llm/enrich/product-paragraph` |
| Mission | `mission_semantic_document` | `POST /v1/llm/mission/semantic-document` |
| Category profile | `user_category_daypart_summary` | `POST /user/category/daypart-summary` |
| Category profile | `user_category_daily_summary` | `POST /user/category/daily-summary` |
| Category profile | `user_category_monthly_summary` | `POST /user/category/monthly-summary` |
| Category profile | `user_category_preference_profile` | `POST /user/category/preference-profile` |
| Basket profile | `user_basket_daypart_summary` | `POST /user/basket/daypart-summary` |
| Basket profile | `user_basket_daily_summary` | `POST /user/basket/daily-summary` |
| Basket profile | `user_basket_monthly_summary` | `POST /user/basket/monthly-summary` |
| Basket profile | `user_basket_profile` | `POST /user/basket/profile` |
| Global profile | `user_global_profile` | `POST /user/global-profile` |
| Feed evaluation | `user_feed_quality_review` | `POST /user/feed-quality-review` |

## Product Enrichment

Product enrichment is a two-stage offline flow:

```text
catalog product
  -> fetch_product_knowledge
  -> structured product identity, use, context, queries, substitutes,
     complements, and candidate mission mappings
  -> product_semantic_paragraph
  -> one dense retrieval paragraph
  -> BGE embedding
```

`fetch_product_knowledge` accepts factual catalog fields such as product title,
brand, category path, merchant description, variant, size, quantity, material,
and sales package. It returns three deliberately separate paragraphs:

- `product_paragraph`: what the product is;
- `intent_paragraph`: general reasons shoppers buy it quickly on Minutes;
- `context_paragraph`: general audience, complement, and usage context.

It also returns normalized product identity, query coverage, mission mappings,
substitutes, complements, decision factors, and substitution tolerance.
Product-use and intent text are general catalog knowledge and must never be
treated as evidence that a particular user had that intent.

`product_semantic_paragraph` compresses the structured enrichment into one
natural retrieval paragraph. This paragraph is the recommended text to embed
for product-to-profile and product-to-mission similarity.

## Mission Enrichment

Mission enrichment operates on an existing canonical mission. It must not
invent, rename, merge, or broaden missions.

```text
canonical mission + structural metadata + representative real products
  -> mission_semantic_document
  -> identity_text
  -> need_state_text
  -> user_context_text
  -> product_scope_text
  -> boundary_text
  -> retrieval_text
  -> BGE embedding
```

Example request:

```json
{
  "mission_name": "Everyday Milk Refill",
  "current_description": "Replenish household milk for regular use.",
  "mission_class": "routine",
  "family": "daily_essentials",
  "dayparts": ["morning", "afternoon", "night"],
  "seasons": [],
  "diet_tags": ["vegetarian"],
  "lifestyle_tags": [],
  "representative_products": [
    {
      "product_name": "Amul Taaza Pasteurised Toned Milk 500 ml",
      "category": "MilkXPlain",
      "general_product_uses": "Tea, coffee, cereal, direct drinking, and cooking."
    }
  ]
}
```

`retrieval_text` is the primary embedding document. The other fields make
mission identity and boundaries inspectable and can support debugging,
generation, and rule-based eligibility checks.

## User-Profile Waterfall

The current flow is daypart-first rather than hourly:

```text
user x category orders
  -> category daypart summary
  -> category daily summary
  -> category monthly summary
  -> user category preference profile

user x complete orders
  -> basket daypart summary
  -> basket daily summary
  -> basket monthly summary
  -> user basket profile

all category profiles + basket profile + recent summaries
  -> user global profile
```

Category profiles retain supported brand, product/variant, pack-size,
ordered-quantity, price/value, timing, replenishment, substitution, and
uncertainty text. Basket profiles retain supported basket breadth,
co-purchases, circumstances, daypart behavior, and candidate shopping needs.
The global profile combines these without erasing category-level detail.

The waterfall does not count the same order again merely because its text
appears at daypart, daily, and monthly levels. Stable behavior requires
repetition across independent dates. One independent date must produce low
behavioral confidence and empty stable-pattern lists.

## Event and Season Context

Stable user profiles do not infer festivals, matchdays, guests, celebrations,
weather, or seasons from timestamps. These are request-time context overlays
provided by an authoritative event/calendar service. Their text can be embedded
with the current user profile to retrieve appropriate missions, but it must not
be written back as a durable user preference without repeated behavioral
evidence.

## Feed Usage

At request time:

1. Select stable category and global profile text.
2. Add recent matching daypart summaries with stronger freshness weight.
3. Add authoritative event/season context when present.
4. Embed the composed retrieval query.
5. Retrieve semantically compatible mission documents.
6. Apply mission eligibility, diversity, and structural-distance constraints.
7. Retrieve products against both the user/category profile and selected
   mission document.
8. Preserve exact/near product affinity before widening to substitutes,
   complements, and discovery.
9. Optionally send the selected feed to `user_feed_quality_review`.

The feed-review task evaluates relevance, diversity, and grounding. It does not
replace deterministic eligibility, inventory, deduplication, or count
requirements.

## Running the Combined Agent

```bash
python app.py \
  --tasks fetch_product_knowledge,product_semantic_paragraph,mission_semantic_document,user_category_daypart_summary,user_category_daily_summary,user_category_monthly_summary,user_category_preference_profile,user_basket_daypart_summary,user_basket_daily_summary,user_basket_monthly_summary,user_basket_profile,user_global_profile,user_feed_quality_review \
  --provider qwen \
  --vllm-url http://rtx-1.dev.internal:8040/v1 \
  --model qwen3.6-35b \
  --port 8091 \
  --max-concurrent 8
```

Use `python app.py --list-tasks` to inspect registration and `GET /openapi.json`
to inspect exact input/output schemas.

## Caching and Inspection

`GET /health` exposes, for every enabled task:

- endpoint;
- model;
- prompt SHA-256;
- input-schema SHA-256;
- output-schema SHA-256;
- combined task-definition SHA-256.

A downstream cache key should include the clean request and combined task
definition hash. The cached result file should contain only the accepted LLM
JSON. Store the exact agent request and execution metadata in separate
inspection files.
