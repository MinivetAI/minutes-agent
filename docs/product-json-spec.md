# Product JSON Spec

This document defines the reduced product-side JSON schema for Flipkart Minutes.

Mission ontology is intentionally out of scope here. This schema is only for:

- product understanding
- product-to-mission mapping
- substitution and complement behavior
- retrieval-oriented paragraphs and query coverage

## Principles

1. Mission internals live in the mission system, not in the product object.
2. The product object only says how a product relates to missions.
3. The schema should support:
   - embeddings
   - retrieval
   - substitution
   - ranking
   - downstream display use cases

## Fields

### 1. `product_paragraph`

Embedding paragraph A.

Purpose:
- explain what the product is
- capture identity, variant logic, and major attributes

### 2. `intent_paragraph`

Embedding paragraph B.

Purpose:
- explain why someone would buy it on Minutes
- capture urgency, interruption, and need-state

### 3. `context_paragraph`

Embedding paragraph C.

Purpose:
- explain who buys it
- explain what it is bought with
- explain the world around the product

### 4. `query_coverage`

Structured natural-language query coverage.

Purpose:
- close vocabulary gaps
- improve retrieval coverage
- separate exact product queries from category, mission, problem, and attribute-led queries

Shape:

```json
{
  "exact_queries": [],
  "category_queries": [],
  "mission_queries": [],
  "problem_queries": [],
  "attribute_queries": []
}
```

### 5. `canonical_name`

Clean normalized product name.

### 6. `product_family`

Broader concept above the SKU.

Examples:
- `Fresh Paneer Blocks`
- `Bridal Bras`
- `Formal Men's Shirts`
- `Panty Liners`

### 7. `summary`

One compact sentence suitable for display contexts.

### 8. `mission_mappings`

List of objects:

```json
{
  "mission_id": "daily_breakfast",
  "centrality": "core"
}
```

Rules:
- `mission_id` is a short snake_case canonical mission identifier
- `centrality` is one of:
  - `core`
  - `strong_supporting`
  - `incidental`

Meaning:
- `core`: mission usually depends on this product or a close equivalent
- `strong_supporting`: materially enables the mission
- `incidental`: may appear in the mission but is not structurally important

### 9. `urgency_signals`

Specific triggers that make someone need the product immediately.

Examples:
- `guests arriving in an hour`
- `charger stopped working`
- `fridge stockout during cooking`
- `need innerwear before leaving for office`

### 10. `gender_applicability`

Allowed values:
- `women`
- `men`
- `girls`
- `boys`
- `babies`
- `unisex`
- `household`
- `not_gendered`

### 11. `household_types`

Buyer or household segments.

Examples:
- `working professionals`
- `families with kids`
- `students`
- `new parents`
- `caregiving households`

### 12. `usage_contexts`

Situational contexts in which the product becomes relevant.

Rules:
- human-readable labels
- situational only
- do not repeat mission IDs or mission labels
- not household segments
- not query phrases

Examples:
- `weekday cooking`
- `office-going`
- `caregiving`
- `pre-wedding`
- `hosting`
- `pooja`

### 13. `brand_sensitivity`

Allowed values:
- `high`
- `medium`
- `low`

### 14. `substitution_tolerance`

Allowed values:
- `low`
- `medium`
- `high`

### 15. `close_substitutes`

Conceptually equivalent or very close substitutes.

### 16. `mission_preserving_substitutes`

Different products that still preserve the user’s underlying mission.

### 17. `common_complements`

Products commonly bought together or for the same occasion.

### 18. `decision_factors`

What buyers consider when choosing among alternatives.

Examples:
- freshness
- fit
- absorbency
- size
- brand trust
- battery life

### Fetch-Time Evidence

`source_urls` may be collected during fetch time as a sidecar evidence object, but it is not part of the production JSON.

## Example Shape

```json
{
  "product_paragraph": "...",
  "intent_paragraph": "...",
  "context_paragraph": "...",
  "query_coverage": {
    "exact_queries": ["amul toned milk 1 litre"],
    "category_queries": ["toned milk", "packaged milk near me"],
    "mission_queries": ["milk for tea", "milk for breakfast"],
    "problem_queries": ["ran out of milk for tea", "need milk for kids before school"],
    "attribute_queries": ["1 litre toned milk", "full cream vs toned milk"]
  },
  "canonical_name": "Toned Milk",
  "product_family": "Packaged Toned Milk",
  "summary": "Everyday packaged milk used for tea, breakfast, cooking, and routine household replenishment.",
  "mission_mappings": [
    {
      "mission_id": "daily_breakfast",
      "centrality": "core"
    },
    {
      "mission_id": "tea_preparation",
      "centrality": "core"
    },
    {
      "mission_id": "hosting_hot_beverages",
      "centrality": "strong_supporting"
    }
  ],
  "urgency_signals": [
    "milk finished before morning tea",
    "children need milk before school",
    "guests want tea and there is no milk at home"
  ],
  "gender_applicability": ["household"],
  "household_types": ["families with kids", "working professionals", "students"],
  "usage_contexts": ["daily routine", "weekday breakfast", "hosting", "weekday cooking"],
  "brand_sensitivity": "medium",
  "substitution_tolerance": "medium",
  "close_substitutes": ["other toned milk brands", "full cream milk", "double toned milk"],
  "mission_preserving_substitutes": ["milk powder", "tetra-pack milk", "curd for some cooking use cases"],
  "common_complements": ["bread", "tea powder", "coffee", "cornflakes", "paneer"],
  "decision_factors": ["freshness", "brand trust", "pack size", "fat content", "price"]
}
```
