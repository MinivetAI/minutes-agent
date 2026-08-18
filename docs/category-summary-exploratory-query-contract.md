# Agent-Owned Category-Jump Query Contract

## Goal

Turn final category summaries into controlled exploratory mission and product
queries. The Minutes Agent owns the approved category-jump graph and uses the
LLM to write retrieval text for only those approved routes.

Examples of the policy are:

```text
Milk + CookiesBiscuits -> Tea, Coffee
Vegetables + Rice -> SpicesMasala, OtherCookingOil
Chips + Chocolates -> AeratedDrinks, FruitDrinks
```

The graph is versioned domain knowledge inside the agent. It is not supplied by
the caller and is not duplicated in inference or feed-service code.

## Flow

```text
final category summary_text values
    -> Minutes Agent selects applicable approved routes
    -> LLM writes mission and product queries for each target category
    -> agent validates route identity, novelty and query vocabulary
    -> approved route-aware output
    -> offline embedding publication
    -> target-category mission and product candidate lanes
```

## LLM input

The external request contains only category names and their final summary text:

```json
{
  "category_summaries": {
    "Milk": "The user repeatedly buys toned milk in smaller packs, often in multiple units.",
    "CookiesBiscuits": "The user regularly buys familiar biscuits for evening snacks."
  }
}
```

The request does not contain a user ID, route map, raw orders, scores, vectors,
storage fields, product candidates or mission candidates. User identity is used
only outside the LLM call for orchestration and storage.

The agent deterministically selects approved routes from the category names and
adds those routes to its internal prompt. Pair routes take precedence over
single-category fallbacks. Observed categories cannot be selected as targets,
and the same target is selected at most once.

## LLM output

```json
{
  "exploratory_routes": [
    {
      "route_id": "milk_cookies_to_tea_coffee",
      "source_categories": ["Milk", "CookiesBiscuits"],
      "target_category": "Tea",
      "mission_queries": [
        "Complete an evening milk-and-biscuit snack with freshly brewed tea.",
        "Prepare a simple hot-drink break to accompany familiar biscuits."
      ],
      "product_queries": [
        "buy loose leaf tea for brewing",
        "purchase black tea bags"
      ]
    },
    {
      "route_id": "milk_cookies_to_tea_coffee",
      "source_categories": ["Milk", "CookiesBiscuits"],
      "target_category": "Coffee",
      "mission_queries": [
        "Create a cafe-style hot beverage to pair with evening biscuits.",
        "Stock a quick coffee option for a weekend snack break."
      ],
      "product_queries": [
        "buy ground coffee beans",
        "purchase instant coffee powder"
      ]
    }
  ]
}
```

Every route is self-contained so the feed service knows the exact target
category for both query types. Each string is embedded separately during
offline publication.

## Validation

The agent rejects and retries an output when:

- a route, source set or target is not in the selected approved graph;
- a target repeats an observed category or another selected target;
- a product query does not explicitly describe its target category;
- a product query leaks the source category and collapses back to known items;
- a required route is missing, duplicated or returned out of contract.

This makes route selection deterministic while leaving the LLM responsible for
clear, varied retrieval language.

## Feed consumption

Each route becomes an independent global sublane:

```text
mission_queries -> mission-vector search -> missions containing target-category products
product_queries -> product-vector search -> products in target_category
```

All global sublanes share one fixed global importance budget. Adding more
routes splits that budget; it does not increase the global source's total
influence. The feed service then performs lane-local deduplication and spacing,
followed by weighted mixing and same-lane backfill.

Mission and product queries remain independent. A route may yield eligible
products even when the current mission catalog has no serviceable mission for
that target category.

## Ownership boundary

- Minutes Agent owns the versioned jump graph, route selection, prompt and
  output validation.
- Inference exposes the agent task without rewriting the request or response.
- The profile pipeline stores the approved output and publishes only the query
  vectors required by feed retrieval.
- The feed service consumes route ID, target category and vectors; it does not
  reconstruct or reinterpret the jump policy.
