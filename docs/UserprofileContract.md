# Minutes User Profile Inference Contract

Status: proposed integration contract
Scope: the request/response contract for every task that builds the category,
basket, and global user profiles, plus how often each should be called.

## 1. Generic Inference Request Model

```json
{
  "mode": "SYNC",
  "taskType": "minutes_user_category_daypart_summary",
  "inputs": {}
}
```

Validation:

- `mode`: required, must be `SYNC` or `ASYNC`
- `taskType`: required
- `inputs`: required

Behavior:

- `SYNC` returns `200 OK` with the upstream JSON body
- `ASYNC` returns `204 No Content`; the result is written to the profile store and does not need to be read back by the caller

### 1.1 The shape of every `inputs` object

Every `inputs` object validates as exactly one task's Pydantic input model
(`models.py`), plus `user_id` for routing to the right profile store. There is
no other generic envelope field.

- The daypart stage is the only stage ever built from this user's raw
  completed orders. The calling system resolves each `product_id` to its
  catalog category/brand/product name and merges repeated order lines into a
  per-product ordered quantity *before* the model is ever called — the model
  is never handed a raw, unaggregated order array.
- Every later stage (daily, monthly, profile) receives only the unmodified
  output array of the immediately preceding stage (`daypart_summaries` /
  `daily_summaries` / `monthly_summaries`) — never a fresh read of raw orders.

## 2. What Flipkart is responsible for supplying

One signal, timestamped: completed orders. Category, basket, and global
profiles are built from completed order history only — never from search,
product-page-view, add-to-cart, or cart-remove activity. This is a deliberate
scope boundary for the stable, batch-refreshed profiles in this contract; it
does not apply to the separate in-session layer described in the
architecture doc, which is out of scope here.

```json
{
  "orders": [
    {
      "order_id": "O778812",
      "timestamp": "2026-07-23T13:05:00+05:30",
      "products": [
        { "product_id": "P90210", "quantity": 1 }
      ]
    }
  ]
}
```

Each `product_id` is resolved to a product name, brand, category, and product
type via our catalog before it is ever written into a summary — Flipkart
sends only the ID and the ordered quantity.

### 2.1 Daypart boundaries (internal, for reference)

| Daypart | Local time |
| --- | --- |
| morning | 05:00–10:59 |
| afternoon | 11:00–15:59 |
| evening | 16:00–20:59 |
| night | 21:00–04:59 |

## 3. Category profile task matrix

`category` is the resolved category name (from `product_id` via our catalog,
before this task is ever called) at the daypart stage, and simply propagates
unchanged through daily → monthly → profile.

| Logical operation | taskType | Configured upstream target | Required inputs |
| --- | --- | --- | --- |
| Category daypart summary | `minutes_user_category_daypart_summary` | `/user/category/daypart-summary` | `user_id, category, date, daypart, day_type, population_daypart_share, order_count, products` |
| Category daily summary | `minutes_user_category_daily_summary` | `/user/category/daily-summary` | `user_id, category, date, day_type, daypart_summaries` |
| Category monthly summary | `minutes_user_category_monthly_summary` | `/user/category/monthly-summary` | `user_id, category, month, daily_summaries` |
| Category preference profile | `minutes_user_category_preference_profile` | `/user/category/preference-profile` | `user_id, category, monthly_summaries` |

`products` is never empty at the daypart stage — a category daypart summary
always requires at least one completed order and at least one resolved
product in this category and window. There is no browsing-only evidence to
summarize without a completed order.

### 3.1 `minutes_user_category_daypart_summary`

Request:

```json
{
  "mode": "SYNC",
  "taskType": "minutes_user_category_daypart_summary",
  "inputs": {
    "user_id": "U123",
    "category": "Dairy",
    "date": "2026-07-23",
    "daypart": "afternoon",
    "day_type": "weekday",
    "population_daypart_share": { "morning": 0.18, "afternoon": 0.34, "evening": 0.31, "night": 0.17 },
    "order_count": 1,
    "products": [
      {
        "product_name": "Amul Taaza Pasteurised Toned Milk 500 ml",
        "category": "Dairy",
        "brand": "Amul",
        "product_type": "Toned milk",
        "quantity": 2,
        "product_paragraph": "Pasteurised toned milk in a 500 ml pouch.",
        "general_product_uses": "A daily household staple used for tea, coffee, and general cooking."
      }
    ]
  }
}
```

`products[].brand` comes from the catalog's own brand field — never parsed or
guessed from `product_name`. `population_daypart_share` is this user's
*population-level* baseline (not their own), supplied so the model can say a
daypart is genuinely distinctive to this user rather than reflecting an
ordinary population-wide pattern.

Output (stored, and forwarded as one entry in the next stage's
`daypart_summaries`; `daypart`/`day_type` are echoed by the model exactly as
supplied):

```json
{
  "daypart": "afternoon",
  "day_type": "weekday",
  "summary_text": "The user purchased two units of Amul toned milk in the afternoon.",
  "preference_claims": [
    { "dimension": "brand", "value": "Amul", "claim_text": "Amul is the purchased brand in this window.", "confidence": "low", "evidence_count": 1, "independent_date_count": 1 }
  ],
  "shopping_context_text": "An afternoon purchase, in line with this user's own typical afternoon activity.",
  "uncertainty_text": "One window cannot establish a repeated brand or timing preference.",
  "overall_confidence": "low",
  "window_evidence": null
}
```

`window_evidence` is always `null` in the model's own response — the calling
system merges it in immediately afterward, directly from this window's raw
orders (`order_count`, this window's own purchase date, first/last-seen
timestamps). This is the *only* stage where `window_evidence` is built from
raw orders; every later stage only ever unions the `window_evidence` its own
inputs already carry (see §1.1).

### 3.2 `minutes_user_category_daily_summary`

Request — `daypart_summaries` is the unmodified array of 3.1's outputs for
that date:

```json
{
  "mode": "SYNC",
  "taskType": "minutes_user_category_daily_summary",
  "inputs": {
    "user_id": "U123",
    "category": "Dairy",
    "date": "2026-07-23",
    "day_type": "weekday",
    "daypart_summaries": [ "... one or more objects shaped exactly like the 3.1 output, window_evidence included ..." ]
  }
}
```

Output:

```json
{
  "date": "2026-07-23",
  "day_type": "weekday",
  "summary_text": "Dairy activity today was a single afternoon Amul toned milk purchase.",
  "daypart_patterns": [
    { "daypart": "afternoon", "pattern_text": "The afternoon purchase is this day's only Dairy activity.", "confidence": "low" }
  ],
  "preference_claims": [],
  "uncertainty_text": "One day of evidence cannot establish a stable pattern.",
  "overall_confidence": "low",
  "window_evidence": null
}
```

`window_evidence` is again always `null` from the model — the calling system
merges in the union of this date's `daypart_summaries[].window_evidence`
afterward.

### 3.3 `minutes_user_category_monthly_summary`

Request — `daily_summaries` is the unmodified array of 3.2's outputs across
the month:

```json
{
  "mode": "SYNC",
  "taskType": "minutes_user_category_monthly_summary",
  "inputs": {
    "user_id": "U123",
    "category": "Dairy",
    "month": "2026-07",
    "daily_summaries": [ "... one or more objects shaped exactly like the 3.2 output ..." ]
  }
}
```

Output (first stage where a claim can be called stable — repetition across
independent dates is now assessable):

```json
{
  "month": "2026-07",
  "summary_text": "Across the month, the user repeatedly purchased Amul toned milk on 9 independent dates.",
  "stable_preference_claims": [
    { "dimension": "brand", "value": "Amul", "claim_text": "Amul is the repeatedly purchased brand.", "confidence": "high", "evidence_count": 14, "independent_date_count": 9 }
  ],
  "temporal_patterns": [
    { "daypart_or_day_type": "afternoon", "pattern_text": "Afternoon purchases recur across the month.", "confidence": "high" }
  ],
  "trend_claims": [],
  "uncertainty_text": "No durable price preference is asserted; no price data is available.",
  "overall_confidence": "high",
  "window_evidence": null
}
```

### 3.4 `minutes_user_category_preference_profile`

Request — `monthly_summaries` is the unmodified array of 3.3's outputs, and
nothing else:

```json
{
  "mode": "SYNC",
  "taskType": "minutes_user_category_preference_profile",
  "inputs": {
    "user_id": "U123",
    "category": "Dairy",
    "monthly_summaries": [ "... one or more objects shaped exactly like the 3.3 output ..." ]
  }
}
```

Output — matches the architecture doc's `categoryProfiles.dairy` example
(§5.1) field-for-field (snake_case here; the architecture doc shows the same
fields camelCased for the served feed API):

```json
{
  "category_name": "Dairy",
  "summary_text": "The user treats Dairy as a routine, near-daily household-continuity category, anchored to Amul toned milk.",
  "preferences": {
    "products": [
      { "product_text": "Amul Taaza Pasteurised Toned Milk 500 ml", "preference_text": "Most consistently repurchased product.", "confidence": "high" }
    ],
    "brands": [
      { "brand": "Amul", "preference_text": "Most consistently selected milk brand.", "confidence": "high", "boundary_text": "This does not establish an Amul preference outside toned milk." }
    ],
    "variants": [],
    "pack_sizes": [],
    "ordered_quantities": []
  },
  "daypart_understanding": [
    { "daypart": "afternoon", "behavior_text": "Afternoon carries the strongest repeated purchase evidence.", "confidence": "high" }
  ],
  "substitution_text": "Prefer toned-milk alternatives before broadening to other milk forms.",
  "uncertainty_text": "No durable price preference is asserted; no price data is available.",
  "retrieval_text": "A routine toned-milk shopper anchored to Amul in 500 ml packs, afternoon-led, not yet extending to other Dairy forms.",
  "replenishment": {
    "cadence_days": 3.2,
    "cadence_class": "fast",
    "predicted_next_purchase_date": "2026-07-26",
    "replenishment_text": "Dairy is reordered roughly every 3 days."
  },
  "evidence": {
    "evidence_count": 14,
    "independent_date_count": 9,
    "first_seen_at": "2026-05-02T09:10:00+05:30",
    "last_seen_at": "2026-07-23T13:05:00+05:30"
  }
}
```

`replenishment` and `evidence` are always left `null` by the model — it is
given no purchase-date data in this call. Both are merged in afterward by the
calling system, computed purely from this category's own accumulated
`window_evidence` (the union of every supplied monthly summary's own
`window_evidence` — never a fresh read of raw orders): `cadence_days` is the
median gap between independent purchase dates, `predicted_next_purchase_date`
is the last purchase date plus that cadence, and `evidence` echoes the
accumulated order count, independent date count, and first/last-seen span.

Replenishment is category-level only — there is no product-level
replenishment field. A specific-SKU "buy it again" signal is built by
combining this category-level cadence with `preferences.brands` /
`.variants` / `.pack_sizes` (which product, at what confidence) rather than
tracking a separate per-product cadence.

## 4. Basket profile task matrix

| Logical operation | taskType | Configured upstream target | Required inputs |
| --- | --- | --- | --- |
| Basket daypart summary | `minutes_user_basket_daypart_summary` | `/user/basket/daypart-summary` | `user_id, date, daypart, day_type, orders, category_pair_evidence` |
| Basket daily summary | `minutes_user_basket_daily_summary` | `/user/basket/daily-summary` | `user_id, date, day_type, daypart_summaries` |
| Basket monthly summary | `minutes_user_basket_monthly_summary` | `/user/basket/monthly-summary` | `user_id, month, daily_summaries` |
| Basket profile | `minutes_user_basket_profile` | `/user/basket/profile` | `user_id, monthly_summaries` |

A basket task is never scoped to one category. `category_pair_evidence` is
precomputed once per user, directly from this user's own raw orders (support,
a numeric co-occurrence confidence, lift, and `co_order_count` for the
categories that most often co-occur in a complete order), and supplied only
at the daypart stage; the model only ever echoes its `support`/`lift` numbers
into the matching `category_combinations` entry, never computes them itself.
There is no abandoned-cart signal anywhere in this waterfall — that concept
required add-to-cart/remove-from-cart events, which are out of scope for this
order-history-only pipeline.

### 4.1 `minutes_user_basket_daypart_summary`

Request:

```json
{
  "mode": "SYNC",
  "taskType": "minutes_user_basket_daypart_summary",
  "inputs": {
    "user_id": "U123",
    "date": "2026-07-23",
    "daypart": "evening",
    "day_type": "weekday",
    "orders": [
      {
        "products": [
          { "product_name": "Britannia Cheese Slices 200 g", "category": "Dairy", "quantity": 1 },
          { "product_name": "Britannia Brown Bread 400 g", "category": "Bakery", "quantity": 1 }
        ]
      }
    ],
    "category_pair_evidence": [
      { "categories": ["Dairy", "Bakery"], "support": 0.086, "confidence": 0.64, "lift": 1.9, "co_order_count": 11 }
    ]
  }
}
```

Output:

```json
{
  "daypart": "evening",
  "day_type": "weekday",
  "basket_summary_text": "The completed order combined Cheese and Brown Bread.",
  "behavior_patterns": [],
  "category_combinations": [
    { "categories": ["Dairy", "Bakery"], "combination_text": "Dairy and Bakery appeared together in this order.", "support": 0.086, "lift": 1.9, "confidence": "medium", "evidence_count": 1, "independent_date_count": 1 }
  ],
  "shopping_need_text": "The completed order supports a small evening top-up.",
  "uncertainty_text": "One order cannot establish a repeated combination pattern on its own.",
  "overall_confidence": "low",
  "window_evidence": null
}
```

Note the two different `confidence` concepts here: `category_pair_evidence[].confidence`
(`0.64`) is a numeric conditional co-occurrence probability computed upstream
from this user's own order history; `category_combinations[].confidence`
(`"medium"`) is the model's own qualitative judgment about how supported this
specific pattern is. The model only ever echoes the former's `support`/`lift`,
never its numeric `confidence`.

### 4.2 `minutes_user_basket_daily_summary`

Request — `daypart_summaries` is the unmodified array of 4.1's outputs:

```json
{
  "mode": "SYNC",
  "taskType": "minutes_user_basket_daily_summary",
  "inputs": {
    "user_id": "U123",
    "date": "2026-07-23",
    "day_type": "weekday",
    "daypart_summaries": [ "... one or more objects shaped exactly like the 4.1 output ..." ]
  }
}
```

Output:

```json
{
  "date": "2026-07-23",
  "day_type": "weekday",
  "summary_text": "Evening activity combined a small completed Cheese-and-Bread order.",
  "daypart_behavior": [
    { "daypart": "evening", "behavior_text": "Evening carries this day's only completed basket.", "confidence": "low" }
  ],
  "behavior_patterns": [],
  "category_combination_patterns": [
    { "categories": ["Dairy", "Bakery"], "combination_text": "Dairy and Bakery appeared together again today.", "support": 0.086, "lift": 1.9, "confidence": "medium", "evidence_count": 1, "independent_date_count": 1 }
  ],
  "shopping_need_text": "Small evening top-up need.",
  "uncertainty_text": "One day cannot establish a recurring pattern.",
  "overall_confidence": "low",
  "window_evidence": null
}
```

### 4.3 `minutes_user_basket_monthly_summary`

Request — `daily_summaries` is the unmodified array of 4.2's outputs across
the month:

```json
{
  "mode": "SYNC",
  "taskType": "minutes_user_basket_monthly_summary",
  "inputs": {
    "user_id": "U123",
    "month": "2026-07",
    "daily_summaries": [ "... one or more objects shaped exactly like the 4.2 output ..." ]
  }
}
```

Output (first stage where a cross-category combination can be called stable,
same as §3.3):

```json
{
  "month": "2026-07",
  "summary_text": "Evening orders repeatedly supported small household top-ups combining Dairy and Bakery.",
  "stable_daypart_behavior": [
    { "daypart": "evening", "behavior_text": "Evening ordering recurs across multiple independent dates this month.", "confidence": "high" }
  ],
  "stable_behavior_patterns": [],
  "category_combination_patterns": [
    { "categories": ["Dairy", "Bakery"], "combination_text": "Dairy and Bakery recur together across the month.", "support": 0.086, "lift": 1.9, "confidence": "high", "evidence_count": 11, "independent_date_count": 8 }
  ],
  "trend_claims": [],
  "shopping_need_text": "Repeated small evening top-ups are the dominant supported need this month.",
  "uncertainty_text": "No durable value or basket-size pattern beyond what is stated here.",
  "overall_confidence": "high",
  "window_evidence": null
}
```

### 4.4 `minutes_user_basket_profile`

Request — `monthly_summaries` is the unmodified array of 4.3's outputs across
however many months of history exist:

```json
{
  "mode": "SYNC",
  "taskType": "minutes_user_basket_profile",
  "inputs": {
    "user_id": "U123",
    "monthly_summaries": [ "... one or more objects shaped exactly like the 4.3 output ..." ]
  }
}
```

Output — a required output of this waterfall, but not an additional serving
key (architecture doc §5.2): generated here, then consumed unmodified as
input when building `userId:global` (§5):

```json
{
  "summary_text": "The user's strongest repeated basket relationship is toned milk with brown bread, usually inside a small replenishment order.",
  "basket_relationships": [
    {
      "anchor_products": ["Amul Taaza Pasteurised Toned Milk 500 ml"],
      "companion_products": ["Brown bread"],
      "categories": ["Dairy", "Bakery"],
      "relationship_text": "Milk and brown bread repeatedly occur in the same complete order.",
      "recommendation_use_text": "When milk is the active need, brown bread can support a separate breakfast or basket-completion mission.",
      "boundary_text": "The evidence does not make every Bakery product relevant to a milk order.",
      "confidence": "medium",
      "evidence": { "evidence_count": 3, "independent_date_count": 3, "first_seen_at": "2026-05-10T19:10:00+05:30", "last_seen_at": "2026-07-20T19:22:00+05:30" }
    }
  ],
  "value_text": "There is insufficient evidence for a stable value or premium basket preference.",
  "basket_size_segment": "small",
  "large_basket_tendency": "low",
  "multi_quantity_tendency": "medium",
  "daypart_understanding": [
    { "daypart": "afternoon", "behavior_text": "The milk-and-bread relationship is strongest in afternoon orders.", "confidence": "medium" },
    { "daypart": "night", "behavior_text": "Night baskets reinforce milk replenishment but provide weaker evidence for bread.", "confidence": "low" }
  ],
  "day_type_understanding": [
    { "day_type": "weekday", "behavior_text": "The repeated relationship is supported on weekdays.", "confidence": "medium" }
  ],
  "uncertainty_text": "The available evidence does not support a fixed shopping mode or broad breakfast preference.",
  "retrieval_text": "A practical household-continuity shopper whose completed orders repeatedly pair toned milk with brown bread, usually in a small evening basket.",
  "evidence": { "evidence_count": 7, "independent_date_count": 5, "first_seen_at": "2026-05-10T19:10:00+05:30", "last_seen_at": "2026-07-23T20:00:00+05:30" },
  "user_id": "U123",
  "artifact_type": "basket_profile",
  "updated_at": "2026-07-23T20:00:00+05:30"
}
```

`basket_size_segment`, `large_basket_tendency`, and `multi_quantity_tendency`
are synthesized by the model itself — the same repetition-across-independent-
dates discipline as every other qualitative field in this contract, judged
from item counts and quantities already visible across the supplied
summaries, never a computed ratio. `evidence`, `user_id`, `artifact_type`, and
`updated_at` are always left `null` by the model; the calling system
merges/stamps all four in afterward — `evidence` from this user's accumulated
`window_evidence`, never a fresh read of raw orders.

## 5. Global profile task

| Logical operation | taskType | Configured upstream target | Required inputs |
| --- | --- | --- | --- |
| Global profile | `minutes_user_global_profile` | `/user/global-profile` | `user_id, category_profiles, basket_profile, recent_summaries, total_category_count` |

Exactly two evidence inputs: every category profile (3.4's output, one per
category) and the one basket profile (4.4's output, unmodified).
`total_category_count` is only supplied when it exceeds the number of
`category_profiles` included (a heavy-tail user capped to their
best-evidenced categories — ranked by `evidence.independent_date_count`, then
`evidence.evidence_count`, never by purchase volume); `recent_summaries` is a
small array of the freshest daypart/daily summary text, for freshness between
refreshes.

Request:

```json
{
  "mode": "SYNC",
  "taskType": "minutes_user_global_profile",
  "inputs": {
    "user_id": "U123",
    "category_profiles": [ "... one 3.4 output per category, unmodified ..." ],
    "basket_profile": "... 4.4's output, unmodified ...",
    "recent_summaries": ["The user's most recent Dairy daily summary text, newest last."],
    "total_category_count": 46
  }
}
```

Output — matches the architecture doc's global-profile example (§5.3)
field-for-field (snake_case here; the architecture doc shows the same fields
camelCased for the served feed API):

```json
{
  "summary_text": "The strongest stable evidence is toned-milk replenishment, with a smaller supported connection to brown bread.",
  "daypart_understanding": [
    { "daypart": "afternoon", "behavior_text": "Milk replenishment is strongest in the afternoon.", "confidence": "high" }
  ],
  "basket_understanding": [
    { "relationship_text": "Milk and brown bread are repeatedly ordered in the same complete basket.", "recommendation_use_text": "A breakfast or replenishment mission may connect these categories without treating every Bakery product as relevant.", "confidence": "medium" }
  ],
  "shopping_style": {
    "frequency_segment": "regular",
    "basket_size_segment": "small",
    "brand_loyalty_level": "high",
    "substitution_tolerance_level": "low",
    "large_basket_tendency": "low",
    "multi_quantity_tendency": "medium",
    "deal_seeking": null,
    "price_sensitivity": null
  },
  "uncertainty_text": "The evidence does not support a broad preference across all Dairy or Bakery products.",
  "retrieval_text": "A routine toned-milk replenishment shopper anchored to Amul in 500 ml packs, afternoon-led, with brown bread as a repeated basket companion.",
  "user_id": "U123",
  "profile_type": "global",
  "updated_at": "2026-07-23T20:00:00+05:30"
}
```

`shopping_style` is a feed-facing behavioral segmentation, built only from
order history:

- `frequency_segment` is always left `null` by the model; the calling system
  computes it afterward from this user's own accumulated order cadence
  (orders per month over the basket profile's own accumulated
  `window_evidence`) — never a fresh read of raw orders, never estimated by
  the model.
- `basket_size_segment`, `large_basket_tendency`, and `multi_quantity_tendency`
  are copied directly from the supplied `basket_profile`'s own same-named
  fields — not resynthesized here.
- `brand_loyalty_level` and `substitution_tolerance_level` are synthesized by
  the model from the supplied category profiles' own order-derived brand
  preferences and substitution boundaries.
- `deal_seeking` and `price_sensitivity` are permanent `null` placeholders
  until price/deal data is available to this pipeline — not fields to guess
  at from other evidence.

`user_id`, `profile_type`, and `updated_at` are always left `null` by the
model; the calling system stamps all three in afterward.

## 6. Occasion-event tasks (festival, matchday — a separate overlay)

| Logical operation | taskType | Configured upstream target | Required inputs |
| --- | --- | --- | --- |
| Occasion occurrence summary | `minutes_user_occasion_event_occurrence_summary` | `/user/occasion/occurrence-summary` | `user_id, occasion_type, occasion_name, basket_summaries, ordinary_baseline_text` |
| Occasion profile | `minutes_user_occasion_event_profile` | `/user/occasion/profile` | `user_id, occasion_type, occurrence_summaries` |

Occasion identity (`occasion_type`) must come from an authoritative calendar
service, never inferred from a timestamp. This overlay is never merged into
the global profile; it is supplied alongside it only when the matching
occasion is active. Refresh trigger: after each labelled occurrence, not on a
clock schedule.

## 7. Response contract

- response type: JSON object, matching the intermediary output shown for that
  `taskType` exactly — field-level typed, no opaque/untyped payload
- a schema change to any response is a versioned, communicated contract
  change, not a silent shape drift
- `ASYNC` mode: no response body; the result is written directly to the
  profile store

## 8. Profile refresh cadence

| Task | Trigger | Notes |
| --- | --- | --- |
| Category/basket daypart summary | As soon as the window closes (past its end time) plus a grace period (1-2 hours) for late delivery | Requires at least one completed order in the window — there is no evidence to summarize without one |
| Category/basket daily summary | Once per calendar day, a few hours after local midnight, for the just-finished day | Not a rolling 24-hour timer — calendar-day aligned, with a buffer for late events |
| Category/basket monthly summary | Rolling: recomputed nightly (or every few days) for the *current, still-open* month using whatever daily summaries exist so far; finalized/locked once the calendar month ends | Treat the open month as mutable, the closed month as immutable and cacheable |
| Category preference profile / basket profile | Same cadence as monthly, since these consume `monthly_summaries` directly | A faster cadence (e.g. nightly) is a cost/freshness trade-off, not a correctness requirement |
| Global profile | Same cadence as the category/basket profiles feeding it | Freshness between regenerations is bridged cheaply via `recent_summaries`, not by regenerating more often |
| Occasion-event tasks | Event-driven: after each labelled occurrence ends | Never on a fixed clock schedule |

Late-arriving orders for an already-closed window (rare, but expected in any
Flipkart integration) require an explicit invalidation step: detect the late
order, delete the affected cached stage's output, and let the next scheduled
run recompute it and everything downstream that depends on it (daily →
monthly → profile → global cascades the same way).

### 8.1 Retention windows

Two independent caps bound how much history ever reaches an LLM call, kept
deliberately different because they protect different things:

- **Daily summaries: ~45 days.** A monthly summary only ever consumes its own
  calendar month's daily summaries (≤31), so this is not an input-shaping
  cap — it is how long the daily-level artifacts need to stay on disk at
  all: enough to finish computing the still-open month plus a buffer for
  late-arriving corrections into the tail of the previous month. Once a
  month is closed and its monthly summary is finalized, its daily summaries
  can be deleted.
- **Monthly summaries: 13-14 months.** This *is* an input-shaping cap: only
  the most recent 13-14 calendar months feed `minutes_user_category_preference_profile`
  and `minutes_user_basket_profile`, oldest months dropped entirely. This is
  a simple recency cap, not a rolling accumulator — `replenishment` and
  `evidence` (§3.4, §4.4) are computed purely from the retained window, so
  `evidence.first_seen_at`/`evidence_count`/cadence reflect this user's
  behavior over the retained 13-14 months, not their full lifetime history.
  A user active for years will show evidence scoped to their recent window,
  by design, in exchange for a call whose size never grows unbounded with
  tenure.

## 9. Integration notes

- Every terminal profile (category, basket, global) expresses what remains
  unknown through its own `uncertainty_text`, not a bolted-on numeric score —
  `overall_confidence` exists only on the daypart/daily/monthly intermediate
  stages, never on a terminal profile.
- `uncertainty_text` is audit-only: no online retrieval or ranking path reads
  it. It forces the model to state scope boundaries in the same response
  where it writes `summary_text`/`retrieval_text` (a grounding discipline,
  not a serving input) and feeds an offline feed-quality-review pass
  (`user_feed_quality_review`) that checks whether a generated feed overclaims
  beyond what a profile supports. The online path only ever reads
  `retrieval_text` (embedded for retrieval) and each claim's `confidence`.
- This pipeline is order-history-only end to end: there is no funnel/
  conversion signal and no abandoned-cart signal anywhere in this waterfall,
  since both would require interaction-event data that is out of scope (§2).
- The source of truth for any field-level question is the intermediary output
  shown for that exact `taskType` above.

## 10. Running/incremental profile tasks (quality-comparison alternative)

This is a second, independent way of building profiles — not part of the
category/basket/global waterfall above, and not merged with it. It exists to
compare profile quality between two fundamentally different strategies on
the same users: deterministic bottom-up aggregation over retained history
(§1-9) versus three profiles each updated in place, order by order.
`scripts/generate_running_user_profiles.py` runs this pipeline standalone,
against the same order-history input as `scripts/generate_user_profiles.py`.

It mirrors the waterfall's own three tiers — category, basket, global — but
replaces each tier's daypart/daily/monthly staging with a single incremental
update per completed order. Critically, the global tier still depends on
the *current* category and basket profiles rather than reading raw orders,
exactly like `GlobalProfileInput` (§5) — only the *mechanism* each tier uses
to stay current (batch retention vs. incremental update) differs between
the two pipelines.

| Logical operation | taskType | Configured upstream target | Required inputs |
| --- | --- | --- | --- |
| Running category profile update | `minutes_user_running_category_profile_update` | `/user/running-profile/category-update` | `user_id, category, new_order, recent_orders, previous_category_profile` |
| Running basket profile update | `minutes_user_running_basket_profile_update` | `/user/running-profile/basket-update` | `user_id, new_order, recent_orders, previous_basket_profile` |
| Running global profile update | `minutes_user_running_profile_update` | `/user/running-profile/update` | `user_id, category_profiles, basket_profile, previous_profile` |

Every completed order triggers, in this dependency order:

1. one **category update** per category the order touched — each sees only
   that category's own rolling window (default 40 of its own past
   order-appearances, `new_order` already filtered to this category's
   products) plus its own `previous_category_profile`;
2. one **basket update** — sees a basket-level rolling window (default 40
   orders, any category, `new_order` unfiltered) plus its own
   `previous_basket_profile`;
3. one **global update** — built from the user's current `category_profiles`
   (every category touched so far, freshly updated for any category this
   order touched) and the fresh `basket_profile`, plus its own
   `previous_profile`. It does not receive raw orders or a rolling window at
   all, matching the waterfall's global profile exactly.

Steps 1 and 2 are mutually independent for the same order and run
concurrently; step 3 waits for both. Across orders, everything is strictly
sequential per tier, since each step depends on that same tier's own
previous output.

### 10.1 Running category profile update

Request (a later order for this category, `previous_category_profile`
populated):

```json
{
  "mode": "SYNC",
  "taskType": "minutes_user_running_category_profile_update",
  "inputs": {
    "user_id": "U123",
    "category": "Dairy",
    "new_order": {
      "date": "2026-07-23",
      "daypart": "afternoon",
      "day_type": "weekday",
      "products": [
        { "product_name": "Amul Taaza Pasteurised Toned Milk 500 ml", "category": "Dairy", "brand": "Amul", "quantity": 2 }
      ]
    },
    "recent_orders": [ "... this category's own prior order-appearances still inside its rolling window, each already filtered to only this category's products, newest last ..." ],
    "previous_category_profile": { "...": "this task's own previous output for this user and category, unmodified" }
  }
}
```

Output — the same shape as `categoryProfiles.<category>` (§5.1) plus one
incremental-only field:

```json
{
  "category_name": "Dairy",
  "summary_text": "The user treats Dairy as a routine, near-daily household-continuity category, anchored to Amul toned milk.",
  "preferences": {
    "products": [ { "product_text": "Amul Taaza Pasteurised Toned Milk 500 ml", "preference_text": "Most consistently repurchased product.", "confidence": "high" } ],
    "brands": [ { "brand": "Amul", "preference_text": "Most consistently selected milk brand.", "confidence": "high", "boundary_text": "This does not establish an Amul preference outside toned milk." } ],
    "variants": [], "pack_sizes": [], "ordered_quantities": []
  },
  "daypart_understanding": [ { "daypart": "afternoon", "behavior_text": "Afternoon carries the strongest repeated purchase evidence.", "confidence": "high" } ],
  "substitution_text": "Prefer toned-milk alternatives before broadening to other milk forms.",
  "change_since_last_text": "Reinforced the existing Amul toned-milk preference with this order; no new claim established.",
  "uncertainty_text": "No durable price preference is asserted; no price data is available.",
  "retrieval_text": "A routine toned-milk shopper anchored to Amul in 500 ml packs, afternoon-led.",
  "replenishment": { "cadence_days": 3.1, "cadence_class": "fast", "predicted_next_purchase_date": "2026-07-26", "replenishment_text": "Dairy is reordered roughly every 3 days." },
  "evidence": { "evidence_count": 40, "independent_date_count": 27, "first_seen_at": "2026-05-14", "last_seen_at": "2026-07-23" }
}
```

`replenishment` and `evidence` are always left `null` by the model, merged
in afterward from this category's own rolling window (never a fresh read of
raw orders) — same discipline as §3.4, just windowed by order count instead
of by a 13-14 month retention cap.

### 10.2 Running basket profile update

Request/output shapes mirror `basket_profile` (§4.4) exactly, plus
`change_since_last_text`; `new_order`/`recent_orders` are unfiltered (every
category in the order). `evidence`, `user_id`, `artifact_type`, and
`updated_at` are always left `null` by the model, merged in afterward from
the basket-level rolling window.

Also included: `category_pair_evidence` (support/confidence/lift/
`co_order_count`, same statistic as §4's `category_pair_evidence`), but
recomputed fresh from the basket-level rolling window on *every* call
instead of once per user's lifetime — never accumulated through this
task's own prior output, so a relationship the model previously failed to
carry forward can be recovered on the very next call rather than staying
lost. `basket_relationships` is capped at the 8 most strongly supported
entries (ranked by `category_pair_evidence`'s `co_order_count` where
covered, otherwise by independent-date repetition) — without this cap, a
user with many categories can produce an unboundedly long response.

### 10.3 Running global profile update

Request — deliberately no raw order field of any kind, same as
`GlobalProfileInput` (§5):

```json
{
  "mode": "SYNC",
  "taskType": "minutes_user_running_profile_update",
  "inputs": {
    "user_id": "U123",
    "category_profiles": [ "... every category touched so far, each shaped exactly like 10.1's output ..." ],
    "basket_profile": { "...": "this round's fresh 10.2 output, unmodified" },
    "previous_profile": { "...": "this task's own previous global output for this user, unmodified" }
  }
}
```

Output — deliberately the same shape as `userId:global` (§5.3) wherever the
concept is the same, so the two pipelines can be compared field-for-field
for the same user:

```json
{
  "summary_text": "The strongest stable evidence is toned-milk replenishment, with a smaller supported connection to brown bread.",
  "daypart_understanding": [ { "daypart": "afternoon", "behavior_text": "Milk replenishment is strongest in the afternoon.", "confidence": "high" } ],
  "basket_understanding": [ { "relationship_text": "Milk and brown bread are repeatedly ordered in the same complete basket.", "recommendation_use_text": "A breakfast or replenishment mission may connect these categories without treating every Bakery product as relevant.", "confidence": "medium" } ],
  "shopping_style": {
    "frequency_segment": "regular",
    "basket_size_segment": "small",
    "brand_loyalty_level": "high",
    "substitution_tolerance_level": "low",
    "large_basket_tendency": "low",
    "multi_quantity_tendency": "medium",
    "deal_seeking": null,
    "price_sensitivity": null
  },
  "change_since_last_text": "Reinforced the existing Dairy-anchored profile; the Bakery connection strengthened with this order.",
  "uncertainty_text": "The evidence does not support a broad preference across all Dairy or Bakery products.",
  "retrieval_text": "A routine toned-milk replenishment shopper anchored to Amul in 500 ml packs, afternoon-led, with brown bread as a repeated basket companion.",
  "user_id": "U123",
  "profile_type": "running",
  "updated_at": "2026-07-23T20:00:00+05:30"
}
```

`shopping_style.basket_size_segment`/`.large_basket_tendency`/
`.multi_quantity_tendency` are copied directly from the supplied
`basket_profile` — not resynthesized here, exactly like the waterfall's
global profile. `frequency_segment` is always left `null` by the model and
merged in afterward by the calling script, from `basket_profile`'s own
accumulated evidence — never a fresh read of raw orders.

### 10.4 What's different from the waterfall

- `change_since_last_text` exists at all three tiers here and nowhere in
  the waterfall — each names what that tier's update reinforced, revised,
  or newly established relative to its own previous output. The waterfall
  has no equivalent, since it rebuilds each profile from full retained
  evidence rather than updating one in place.
- Every tier's `evidence` is scoped to a rolling window measured in orders
  (default 40, per-category for category profiles, any-category for the
  basket profile), not a 13-14 month retention cap — it ages out order by
  order rather than month by month.
- The global tier's dependency on `category_profiles` + `basket_profile`
  (never raw orders, never even the triggering order itself) is identical in
  spirit to the waterfall's `GlobalProfileInput` — the comparison between
  pipelines is meant to isolate "batch aggregation vs. incremental update"
  as the actual variable under test, not "does global synthesize from lower
  tiers."
- If any tier's update call fails for one order, that tier's in-memory state
  simply carries forward unchanged — the calling script never resets it,
  never substitutes a stand-in, and never falls back to reading raw orders
  to compensate. A category or basket profile that fails to update this
  round stays exactly as it was after its last successful update; the
  global update (and every later round) proceeds using that same
  last-known-good snapshot. The only case where a round's global update is
  skipped outright is when a category or the basket profile has *never*
  once succeeded for this user yet (nothing to fall back to).

None of these three tasks are ever called from `generate_user_profiles.py`
and none feed `userId:global`; this is a standalone comparison pipeline, run
and evaluated independently (e.g. by pointing `user_feed_quality_review` at
each pipeline's per-tier output for the same user and comparing scores).
