# Minutes User Profile Contract

Status: proposed contract for team review
Date: 2026-07-24
Scope: LLM inputs and outputs for user-profile generation only. Deterministic computation — counts, cadence, lift, funnel-conversion rates — is performed upstream by the recommendation service or offline pipeline and supplied to the LLM as input; ranking, weighting, and serving-time decisions are performed downstream by the Feed Service. This contract defines only what sits between those two: what the LLM receives, and what it must return.

## 1. Decision

Build the Minutes user profile from two evidence pipelines, plus one separate contextual overlay:

```text
user x category evidence (orders, searches, product views, cart adds/removes)
  -> category daypart summary
  -> category daily summary
  -> category monthly summary
  -> user category profile

user x complete orders and assembled-but-abandoned carts
  -> basket daypart summary
  -> basket daily summary
  -> basket monthly summary
  -> user basket-context profile

user category profiles[] + user basket-context profile
  -> user global profile
```

A user's interaction with a category is not limited to completed purchases. Searching for a product, viewing its page, adding it to cart, and removing it from cart are all evidence about that category, at different strengths of conviction. All of it belongs in the category pipeline (and, where it concerns a whole basket being assembled, in the basket pipeline) rather than in a separate structure. A category can produce a daypart summary purely from browsing, with zero completed orders.

Occasions — a festival, a cricket match, a guest visit — are a different kind of evidence and are handled separately:

```text
user's occasion-labelled basket summaries for one occurrence
  -> occasion-event occurrence summary

occasion-event occurrence summary[] for one occasion type
  -> user occasion-event profile
```

An occasion-event profile is not merged into the global profile. It is supplied as a separate overlay at generation time, alongside the global profile and current context, when a relevant occasion is active.

| Profile | Primary question |
| --- | --- |
| Category profile | What does the user prefer inside this category, and how reliably does interest here convert to a purchase? |
| Basket-context profile | What need is the user solving, and how do they construct — or abandon — orders in different circumstances? |
| Occasion-event profile | How does the user's behavior change during a particular recurring occasion? |
| Global profile | What stable, cross-category understanding can be safely retained and handed to the Feed Service? |

## 2. Scope boundaries

This document defines the unit represented by each LLM call, the JSON input supplied, the JSON output returned, what is passed to the next stage, and the evidence/confidence/inference rules that govern all of it. It does not define storage technology, serving keys, embedding models, ranking weights, scheduling, or the Feed Service's own logic — only the contract at its boundary.

## 3. Canonical language

### 3.1 Time buckets

| Daypart | Local time |
| --- | --- |
| morning | 05:00–10:59 |
| afternoon | 11:00–15:59 |
| evening | 16:00–20:59 |
| night | 21:00–04:59 |

`unknown` may be used during ingestion fallback but must never be emitted as a stable learned daypart preference.

### 3.2 Categories

`category` means the product's actual Minutes analytical vertical (e.g. `Milk`, `CleaningSupplies`, `IceCreams`) — never a generic umbrella like `Food`.

### 3.3 Funnel stages

```text
funnel_stage:        viewed | searched | added_to_cart | removed_from_cart | purchased
funnel_stage_weight: viewed=0.1, searched=0.2, added_to_cart=0.4, removed_from_cart=-0.2, purchased=1.0
```

This ordering is a fixed evidence-strength prior. A view is not equivalent evidence to a purchase, and none of these stages may be narrated with the same certainty language as a completed purchase.

### 3.4 Shared enums

```json
{
  "daypart": ["morning", "afternoon", "evening", "night"],
  "day_type": ["weekday", "weekend"],
  "confidence": ["low", "medium", "high"],
  "trend": ["stable", "emerging", "reinforced", "declining"],
  "cadence_class": ["fast", "medium", "slow", "unknown"],
  "event_relationship": ["unrelated", "possibly_related", "likely_related"]
}
```

## 4. Shared rules

Every profile-generation prompt in this contract enforces the following:

- Use only supplied products, funnel events, catalog attributes, summaries, and context labels. Never invent categories, brands, pack sizes, quantities, prices, occasions, or behavioral counts.
- A view is the weakest evidence; a search is stronger and carries explicit stated intent; an add-to-cart is stronger still; a purchase is the strongest. Repeated add-to-cart without purchase is evidence of interest, not preference, and not proof of any specific blocker — a cause (price, stock, hesitation) may be offered only as a labeled hypothesis. Repeated search or viewing with zero purchases is unmet interest, a discovery signal, and never grounds to suppress a category.
- Treat one occurrence as weak evidence. "Stable", "repeated", "routine", and "typically" require repetition across independent dates; the number of independent dates required scales with the category's supplied cadence — a fast-moving category needs more repetitions to rule out noise, a slow-moving one needs fewer but a longer elapsed span.
- Every claim-bearing block carries `evidence_count`, `independent_date_count`, `first_observed_date`, and `last_observed_date` alongside its text and confidence enum. These are aggregate counts, not order or event identifiers.
- Daypart, day-type, and cadence claims are expressed relative to a supplied baseline — population daypart share, or the user's own observed cadence for that category — never as an unanchored adjective the model chooses on its own.
- The calling service supplies deterministic counts, cadences, and lift/support numbers as input. The LLM explains what they mean; it never calculates, re-derives, or invents them, and it never emits a numeric score or ranking weight of its own.
- If a required attribute is absent, return an empty list or null; do not infer it from general world knowledge.
- Never infer protected, demographic, medical, financial, or psychological characteristics. Describe shopping behavior, not personal identity.
- Return only schema-valid JSON.

## 5. Pipeline A: user category profile

### 5.1 Flow and responsibility

```text
user x category x daypart x date (orders + funnel events)
  -> CategoryDaypartSummary
CategoryDaypartSummary[] for one date and category
  -> CategoryDailySummary
CategoryDailySummary[] for one month and category
  -> CategoryMonthlySummary
CategoryMonthlySummary[] for one category
  -> UserCategoryProfile
```

The category profile owns brand, product, variant, pack-size, ordered-quantity, replenishment cadence, substitution, and interest-to-purchase conversion inside one category. It does not own cross-category basket intent.

### 5.2 Category daypart summary

Input:

```json
{
  "category": "IceCreams",
  "date": "2026-07-23",
  "daypart": "evening",
  "day_type": "weekday",
  "population_daypart_share": {"morning": 0.32, "afternoon": 0.25, "evening": 0.30, "night": 0.12},
  "order_count": 0,
  "orders": [],
  "funnel_events": [
    {"stage": "searched", "query_text": "chocolate ice cream tub"},
    {"stage": "viewed", "product_name": "Amul Chocolate Ice Cream Tub 750 ml", "view_count": 3},
    {"stage": "added_to_cart", "product_name": "Amul Chocolate Ice Cream Tub 750 ml", "quantity": 1},
    {"stage": "removed_from_cart", "product_name": "Amul Chocolate Ice Cream Tub 750 ml"}
  ]
}
```

`order_count` may be zero — a category can be represented purely by browsing and search behavior. `orders`, when present, carry the same product evidence (name, brand, pack, quantity) as a completed purchase.

Output:

```json
{
  "daypart": "evening",
  "day_type": "weekday",
  "summary_text": "The user searched for and viewed a chocolate ice cream tub, added it to cart, and removed it before checkout; no purchase occurred in this category this evening.",
  "preference_claims": [
    {
      "dimension": "product",
      "value": "Amul Chocolate Ice Cream Tub 750 ml",
      "claim_text": "Repeated viewing indicates interest in this specific product.",
      "confidence": "low",
      "evidence_count": 1,
      "independent_date_count": 1
    }
  ],
  "funnel_signal": {
    "highest_stage_reached": "added_to_cart",
    "converted": false,
    "signal_text": "Interest reached cart level but did not convert to a purchase in this session.",
    "confidence": "low"
  },
  "shopping_context_text": "Observed timing and general product utility, without claiming why this specific user searched for it.",
  "uncertainty_text": "One session cannot establish a repeated interest or non-conversion pattern.",
  "overall_confidence": "low"
}
```

### 5.3 Category daily summary

Input: the day's daypart summaries for one category, unchanged from §5.2's output.

```json
{
  "category": "IceCreams",
  "date": "2026-07-23",
  "day_type": "weekday",
  "daypart_summaries": [
    {
      "daypart": "evening",
      "day_type": "weekday",
      "summary_text": "The user searched for and viewed a chocolate ice cream tub, added it to cart, and removed it before checkout; no purchase occurred in this category this evening.",
      "preference_claims": [
        {
          "dimension": "product",
          "value": "Amul Chocolate Ice Cream Tub 750 ml",
          "claim_text": "Repeated viewing indicates interest in this specific product.",
          "confidence": "low",
          "evidence_count": 1,
          "independent_date_count": 1
        }
      ],
      "funnel_signal": {
        "highest_stage_reached": "added_to_cart",
        "converted": false,
        "signal_text": "Interest reached cart level but did not convert to a purchase in this session.",
        "confidence": "low"
      },
      "shopping_context_text": "Observed timing and general product utility, without claiming why this specific user searched for it.",
      "uncertainty_text": "One session cannot establish a repeated interest or non-conversion pattern.",
      "overall_confidence": "low"
    }
  ]
}
```

Output:

```json
{
  "date": "2026-07-23",
  "day_type": "weekday",
  "summary_text": "IceCreams interest appeared once this evening without conversion.",
  "daypart_patterns": [
    {"daypart": "evening", "pattern_text": "Evening browsing included unconverted ice-cream interest.", "confidence": "low"}
  ],
  "preference_claims": [],
  "uncertainty_text": "One day of evidence.",
  "overall_confidence": "low"
}
```

### 5.4 Category monthly summary

Input: the month's daily summaries for one category, unchanged from §5.3's output (typically 15-30 entries; one shown here for brevity).

```json
{
  "category": "IceCreams",
  "month": "2026-07",
  "daily_summaries": [
    {
      "date": "2026-07-23",
      "day_type": "weekday",
      "summary_text": "IceCreams interest appeared once this evening without conversion.",
      "daypart_patterns": [
        {"daypart": "evening", "pattern_text": "Evening browsing included unconverted ice-cream interest.", "confidence": "low"}
      ],
      "preference_claims": [],
      "uncertainty_text": "One day of evidence.",
      "overall_confidence": "low"
    }
  ]
}
```

Output:

```json
{
  "month": "2026-07",
  "summary_text": "Across the month, IceCreams was searched and cart-added on 4 independent dates without a completed purchase.",
  "stable_preference_claims": [
    {"dimension": "product", "value": "Amul Chocolate Ice Cream Tub 750 ml", "claim_text": "Repeatedly searched and viewed across independent dates.", "confidence": "medium", "evidence_count": 5, "independent_date_count": 4}
  ],
  "temporal_patterns": [
    {"daypart_or_day_type": "evening", "pattern_text": "Interest concentrates in evening sessions.", "confidence": "medium"}
  ],
  "trend_claims": [],
  "uncertainty_text": "The cause of non-conversion cannot be established without a price or inventory feed.",
  "overall_confidence": "medium"
}
```

### 5.5 User category profile

Input: monthly summaries for one category, plus one deterministic replenishment field the LLM does not compute:

```json
{
  "category": "Milk",
  "observed_cadence_days": 3.2,
  "observed_cadence_evidence_count": 14,
  "observed_cadence_independent_date_count": 9,
  "observed_last_purchase_date": "2026-07-20",
  "observed_predicted_next_purchase_date": "2026-07-23",
  "monthly_summaries": ["... CategoryMonthlySummary for Milk ..."]
}
```

`observed_predicted_next_purchase_date` is `observed_last_purchase_date + observed_cadence_days`, computed upstream by plain date arithmetic — the LLM is never asked to add days to a date.

Output:

```json
{
  "category": "Milk",
  "profile_text": "The user treats Milk as a routine, near-daily household-continuity category, most active on weekday mornings.",
  "brand_preferences": [
    {"brand": "Amul", "preference_text": "Most consistently selected milk brand.", "confidence": "high", "evidence_count": 12, "independent_date_count": 8}
  ],
  "product_preferences": [
    {"preference_text": "Toned milk is the most consistently selected variant.", "examples": ["Amul Taaza Toned Milk 500 ml"], "confidence": "high"}
  ],
  "quantity_preferences": [],
  "temporal_preferences": [
    {"daypart_or_day_type": "morning", "preference_text": "Milk demand is well above the population morning baseline.", "affinity_ratio": 2.1, "confidence": "high"}
  ],
  "replenishment": {
    "cadence_days": 3.2,
    "cadence_class": "fast",
    "last_purchase_date": "2026-07-20",
    "predicted_next_purchase_date": "2026-07-23",
    "replenishment_text": "Milk is reordered roughly every 3 days, one of the fastest, most routine categories in this user's basket; last bought 2026-07-20, next due around 2026-07-23.",
    "confidence": "high",
    "evidence_count": 14,
    "independent_date_count": 9
  },
  "discovery_candidate": null,
  "conversion_text": "Purchases in this category are consistent and reliable; there is no unconverted browsing pattern to report.",
  "substitution_text": "Brand loyalty is high; substitution should stay within Amul when possible.",
  "price_value_text": null,
  "emerging_preferences": [],
  "avoidance_or_uncertainty_text": "No durable price or deal-seeking preference is asserted; no price data is available.",
  "mission_generation_text": "Prefer familiar morning milk-replenishment missions, anchored to Amul.",
  "overall_confidence": "high"
}
```

The same call for a category with no purchases yet, only browsing:

```json
{
  "category": "IceCreams",
  "profile_text": "The user shows a repeated, unconverted interest in premium ice cream.",
  "brand_preferences": [],
  "product_preferences": [],
  "quantity_preferences": [],
  "temporal_preferences": [
    {"daypart_or_day_type": "evening", "preference_text": "Browsing activity concentrates in the evening, above the population evening baseline.", "affinity_ratio": 1.4, "confidence": "medium"}
  ],
  "replenishment": {
    "cadence_days": null,
    "cadence_class": "unknown",
    "last_purchase_date": null,
    "predicted_next_purchase_date": null,
    "replenishment_text": "No purchase cadence can be established; this category has not yet converted.",
    "confidence": "low",
    "evidence_count": 5,
    "independent_date_count": 4
  },
  "discovery_candidate": {
    "is_candidate": true,
    "candidate_text": "Repeated search, view, and cart interest with zero completed purchases across 4 independent dates.",
    "confidence": "medium",
    "evidence_count": 5,
    "independent_date_count": 4
  },
  "conversion_text": "Interest in this category has not yet converted to a purchase; treat as a discovery signal, not an established preference.",
  "substitution_text": null,
  "price_value_text": null,
  "emerging_preferences": [],
  "avoidance_or_uncertainty_text": "The reason for non-conversion (price, stock, hesitation) cannot be established from this evidence.",
  "mission_generation_text": "Surface discovery/nudge content for ice cream rather than a replenishment mission.",
  "overall_confidence": "medium"
}
```

`cadence_days` and `cadence_class` are always echoed from the supplied input, never computed by the LLM. `discovery_candidate` and `conversion_text` occupy the same role for every category: describing whether observed interest reliably becomes a purchase.

## 6. Pipeline B: user basket-context profile

### 6.1 Flow and responsibility

```text
complete orders + assembled-but-abandoned carts, for user x daypart x date
  -> BasketDaypartSummary
BasketDaypartSummary[] for one date
  -> BasketDailySummary
BasketDailySummary[] for one month
  -> BasketMonthlySummary
BasketMonthlySummary[]
  -> UserBasketContextProfile
```

The basket pipeline owns need states, category combinations — both completed and abandoned — order-building behavior, repeated daypart behavior, and circumstance-dependent shopping modes. Product lines from the same order, or the same abandoned cart, remain together.

### 6.2 Basket daypart summary

Input:

```json
{
  "date": "2026-07-23",
  "daypart": "evening",
  "day_type": "weekday",
  "orders": [
    {"products": [{"product_name": "Britannia Cheese Slices 200 g", "category": "Cheese", "quantity": 1}]}
  ],
  "abandoned_carts": [
    {"products": [{"product_name": "Amul Chocolate Ice Cream Tub 750 ml", "category": "IceCreams", "quantity": 1}]}
  ],
  "category_pair_evidence": [
    {"categories": ["Milk", "Vegetables"], "support": 0.41, "confidence": 0.63, "lift": 1.8, "co_order_count": 22}
  ]
}
```

Output:

```json
{
  "daypart": "evening",
  "day_type": "weekday",
  "basket_summary_text": "The completed order was a single Cheese item; a separate cart containing an ice-cream tub was assembled but abandoned.",
  "behavior_patterns": [],
  "category_combinations": [
    {"categories": ["Milk", "Vegetables"], "combination_text": "Milk and Vegetables are frequently purchased together.", "support": 0.41, "lift": 1.8, "confidence": "high"}
  ],
  "abandonment_patterns": [
    {"categories": ["IceCreams"], "abandonment_text": "A single-item ice-cream cart was assembled and not checked out.", "confidence": "low", "evidence_count": 1, "independent_date_count": 1}
  ],
  "shopping_need_text": "The completed order supports a small evening top-up; the abandoned cart suggests a separate, unresolved snack interest.",
  "uncertainty_text": "One session cannot establish a repeated abandonment pattern.",
  "overall_confidence": "low"
}
```

### 6.3 Basket daily summary

Input: the day's daypart basket summaries, unchanged from §6.2's output.

```json
{
  "date": "2026-07-23",
  "day_type": "weekday",
  "daypart_summaries": [
    {
      "daypart": "evening",
      "day_type": "weekday",
      "basket_summary_text": "The completed order was a single Cheese item; a separate cart containing an ice-cream tub was assembled but abandoned.",
      "behavior_patterns": [],
      "category_combinations": [
        {"categories": ["Milk", "Vegetables"], "combination_text": "Milk and Vegetables are frequently purchased together.", "support": 0.41, "lift": 1.8, "confidence": "high"}
      ],
      "abandonment_patterns": [
        {"categories": ["IceCreams"], "abandonment_text": "A single-item ice-cream cart was assembled and not checked out.", "confidence": "low", "evidence_count": 1, "independent_date_count": 1}
      ],
      "shopping_need_text": "The completed order supports a small evening top-up; the abandoned cart suggests a separate, unresolved snack interest.",
      "uncertainty_text": "One session cannot establish a repeated abandonment pattern.",
      "overall_confidence": "low"
    }
  ]
}
```

Output:

```json
{
  "date": "2026-07-23",
  "day_type": "weekday",
  "summary_text": "The day's order activity was concentrated in the evening: a small completed Cheese order alongside a separate, abandoned ice-cream cart.",
  "daypart_behavior": [
    {"daypart": "evening", "behavior_text": "Evening activity combined a small completed order with an unresolved snack cart.", "confidence": "low", "evidence_count": 1, "independent_date_count": 1}
  ],
  "behavior_patterns": [],
  "category_combination_patterns": [
    {"categories": ["Milk", "Vegetables"], "combination_text": "Milk and Vegetables recur together.", "support": 0.41, "lift": 1.8, "confidence": "high"}
  ],
  "abandonment_patterns": [
    {"categories": ["IceCreams"], "abandonment_text": "The evening ice-cream cart was not checked out.", "confidence": "low", "evidence_count": 1, "independent_date_count": 1}
  ],
  "shopping_need_text": "The day supports a small evening top-up need; the ice-cream cart remains an open, unresolved interest.",
  "uncertainty_text": "One day cannot establish a recurring abandonment pattern.",
  "overall_confidence": "low"
}
```

### 6.4 Basket monthly summary

Input: the month's daily basket summaries, unchanged from §6.3's output (typically 15-30 entries; one shown here for brevity).

```json
{
  "month": "2026-07",
  "daily_summaries": [
    {
      "date": "2026-07-23",
      "day_type": "weekday",
      "summary_text": "The day's order activity was concentrated in the evening: a small completed Cheese order alongside a separate, abandoned ice-cream cart.",
      "daypart_behavior": [
        {"daypart": "evening", "behavior_text": "Evening activity combined a small completed order with an unresolved snack cart.", "confidence": "low", "evidence_count": 1, "independent_date_count": 1}
      ],
      "behavior_patterns": [],
      "category_combination_patterns": [
        {"categories": ["Milk", "Vegetables"], "combination_text": "Milk and Vegetables recur together.", "support": 0.41, "lift": 1.8, "confidence": "high"}
      ],
      "abandonment_patterns": [
        {"categories": ["IceCreams"], "abandonment_text": "The evening ice-cream cart was not checked out.", "confidence": "low", "evidence_count": 1, "independent_date_count": 1}
      ],
      "shopping_need_text": "The day supports a small evening top-up need; the ice-cream cart remains an open, unresolved interest.",
      "uncertainty_text": "One day cannot establish a recurring abandonment pattern.",
      "overall_confidence": "low"
    }
  ]
}
```

Output:

```json
{
  "month": "2026-07",
  "summary_text": "Across the month, evening orders repeatedly supported small household top-ups, while an ice-cream cart was assembled and abandoned on multiple independent dates.",
  "stable_daypart_behavior": [
    {"daypart": "evening", "behavior_text": "Evening ordering is repeated and above the population baseline.", "confidence": "high", "evidence_count": 14, "independent_date_count": 12}
  ],
  "stable_behavior_patterns": [
    {"behavior_text": "Baskets stay small and need-completing rather than broad discovery baskets.", "circumstance_text": "Weekday evenings.", "confidence": "high", "evidence_count": 14, "independent_date_count": 12}
  ],
  "category_combination_patterns": [
    {"categories": ["Milk", "Vegetables"], "combination_text": "Milk and Vegetables recur together across the month.", "support": 0.41, "lift": 1.8, "confidence": "high"}
  ],
  "abandonment_patterns": [
    {"categories": ["IceCreams"], "abandonment_text": "An ice-cream cart is repeatedly assembled and abandoned across independent dates.", "confidence": "medium", "evidence_count": 4, "independent_date_count": 3}
  ],
  "trend_claims": [],
  "shopping_need_text": "Repeated small evening top-ups are the dominant supported need this month.",
  "uncertainty_text": "The cause of the repeated ice-cream cart abandonment remains unestablished.",
  "overall_confidence": "high"
}
```

### 6.5 User basket-context profile

Input: the accumulated monthly basket summaries, unchanged from §6.4's output.

```json
{
  "monthly_summaries": ["... BasketMonthlySummary for 2026-07 ..."]
}
```

Output:

```json
{
  "profile_text": "The user primarily builds small, practical evening baskets around household staples, with an occasional unresolved snack cart.",
  "behavior_patterns": [
    {"behavior_text": "Evening orders are typically small and need-completing.", "circumstance_text": "Weekday evenings.", "confidence": "high", "evidence_count": 18, "independent_date_count": 14}
  ],
  "daypart_behavior": [
    {"daypart": "evening", "behavior_text": "Evening ordering activity is above the population evening baseline.", "affinity_ratio": 1.3, "confidence": "high"}
  ],
  "basket_structure_text": "Baskets are generally small (2-4 lines) and practical rather than broad discovery baskets.",
  "circumstance_patterns": [],
  "category_combination_patterns": [
    {"categories": ["Milk", "Vegetables"], "combination_text": "Milk and Vegetables recur together across many orders.", "support": 0.41, "lift": 1.8, "confidence": "high"}
  ],
  "abandonment_patterns": [
    {"categories": ["IceCreams"], "abandonment_text": "Ice-cream carts are repeatedly assembled and abandoned rather than checked out.", "confidence": "medium", "evidence_count": 4, "independent_date_count": 3}
  ],
  "mission_generation_text": "Prioritize small evening top-up and household-staple completion missions; ice cream is a candidate for cart-recovery, not a stable preference.",
  "uncertainty_text": "The reason ice-cream carts are abandoned cannot be established without price or inventory data.",
  "overall_confidence": "high"
}
```

## 7. Pipeline C: user occasion-event profile

### 7.1 Flow and responsibility

```text
occasion-labelled basket summaries for one occurrence
  -> OccasionEventOccurrenceSummary
OccasionEventOccurrenceSummary[] for one occasion type
  -> UserOccasionEventProfile
```

Authoritative occasion identity (a cricket match, a festival) is supplied by an authoritative calendar. The LLM may assess whether an order is related to the occasion, but must not invent an active occasion from product behavior alone. This pipeline is distinct from the funnel evidence in Pipelines A and B: a completed occasion-related order is still an order the basket pipeline sees, but "was this evening's snack purchase related to tonight's match" is a comparison against the user's own ordinary baseline that only this pipeline makes.

### 7.2 Occasion-event occurrence summary

Input:

```json
{
  "occasion_type": "cricket_match",
  "occasion_name": "Cricket match",
  "basket_summaries": [
    {"daypart": "evening", "basket_summary_text": "The order combined ready-to-consume snacks and chilled beverages.", "occasion_relationship": "likely_related"}
  ],
  "ordinary_baseline_text": "Ordinary evening baskets are more often focused on cooking staples and household replenishment."
}
```

Output:

```json
{
  "occasion_type": "cricket_match",
  "occurrence_summary_text": "During this match, the user shifted toward ready-to-consume snacks and chilled beverages in the evening.",
  "behavior_delta_text": "This differed from the user's ordinary cooking- and replenishment-led evening behavior.",
  "category_shifts": [
    {"category": "Chips", "shift_text": "Snack demand appeared stronger than the ordinary baseline.", "confidence": "medium"}
  ],
  "uncertainty_text": "One occurrence is insufficient to establish a persistent matchday preference.",
  "overall_confidence": "medium"
}
```

### 7.3 User occasion-event profile

Input: the accumulated occurrence summaries for one occasion type, unchanged from §7.2's output.

```json
{
  "occasion_type": "cricket_match",
  "occurrence_summaries": [
    {
      "occasion_type": "cricket_match",
      "occurrence_summary_text": "During this match, the user shifted toward ready-to-consume snacks and chilled beverages in the evening.",
      "behavior_delta_text": "This differed from the user's ordinary cooking- and replenishment-led evening behavior.",
      "category_shifts": [
        {"category": "Chips", "shift_text": "Snack demand appeared stronger than the ordinary baseline.", "confidence": "medium"}
      ],
      "uncertainty_text": "One occurrence is insufficient to establish a persistent matchday preference.",
      "overall_confidence": "medium"
    }
  ]
}
```

Output:

```json
{
  "occasion_type": "cricket_match",
  "profile_text": "During cricket matches, the user shifts from ordinary cooking and replenishment baskets toward immediately consumable snacks and beverages.",
  "category_signals": [
    {"category": "Chips", "preference_text": "Ready-to-consume snacks become more relevant during match occasions.", "confidence": "medium", "evidence_count": 3, "independent_date_count": 3}
  ],
  "mission_generation_text": "When a cricket match is active, consider match-viewing snack and chilled-beverage missions without replacing the user's stable preferences.",
  "uncertainty_text": "Apply this profile only when the matching occasion is active and supported by sufficient occurrence evidence.",
  "overall_confidence": "medium"
}
```

If there is no meaningful evidence for a user and occasion type, a profile should not be created; the downstream system may fall back to a generic occasion understanding, clearly separated from learned user behavior.

## 8. User global profile

### 8.1 Input

```json
{
  "category_profiles": ["... UserCategoryProfile for every category with sufficient evidence ..."],
  "basket_profile": { "...": "UserBasketContextProfile" },
  "recent_summaries": ["Recent clean category or basket daypart/daily summary text, newest last, for freshness weighting"]
}
```

No other input feeds this call. Freshness overlays (`recent_summaries`) are the same two pipelines' recent leaf-level text, injected directly because batch-computed profiles may lag by up to a compute cycle — not a third profile.

### 8.2 Output

```json
{
  "profile_text": "The user is a routine-oriented quick-commerce shopper, anchored to near-daily milk and produce replenishment, with a separate unresolved interest in premium ice cream.",
  "category_preference_text": "Milk and Vegetables are fast-moving, brand-anchored staples; Cheese converts reliably in smaller volume; IceCreams shows repeated interest without conversion; Cleaning Supplies moves far more slowly than any food category.",
  "basket_context_text": "The user builds small, practical evening baskets and occasionally assembles, then abandons, a snack-focused cart.",
  "replenishment_summary_text": "Milk is the user's fastest-moving category at roughly every 3 days; Vegetables follow close behind. Cleaning Supplies is the slowest observed category. IceCreams has no established cadence because it has not yet converted to a purchase.",
  "structured_signals": [
    {"signal_type": "replenishment_cadence", "category_or_mission": "Milk", "confidence": "high", "source": "category_profile", "rationale_text": "Milk is reordered roughly every 3 days, the fastest cadence among this user's categories."},
    {"signal_type": "replenishment_cadence", "category_or_mission": "CleaningSupplies", "confidence": "medium", "source": "category_profile", "rationale_text": "Cleaning supplies are reordered far less often than the user's daily-essentials categories."},
    {"signal_type": "discovery_candidate", "category_or_mission": "IceCreams", "confidence": "medium", "source": "category_profile", "rationale_text": "Repeated search and cart interest with zero completed purchases."},
    {"signal_type": "cart_recovery", "category_or_mission": "IceCreams", "confidence": "low", "source": "basket_profile", "rationale_text": "A recent cart containing this category was assembled and abandoned."},
    {"signal_type": "cross_category_pattern", "category_or_mission": "daily_essentials_replenishment", "confidence": "high", "source": "category_profile+basket_profile", "rationale_text": "Milk/Vegetables category affinity and small, practical evening baskets jointly support routine household continuity."}
  ],
  "mission_generation_text": "Prioritize daily essentials replenishment (Milk, Vegetables) and small evening top-up missions; surface ice-cream discovery/cart-recovery content as a secondary, exploratory signal.",
  "uncertainty_text": "Do not generalize the IceCreams browsing pattern into a stable preference, and do not assert a reason for its non-conversion.",
  "overall_confidence": "high"
}
```

Rules specific to this task:

- `category_preference_text` must represent every supplied category profile, not only the strongest one.
- `replenishment_summary_text` compares cadence across every supplied category profile — including naming any `cadence_class: "unknown"` categories rather than omitting them — using only the `cadence_days`/`cadence_class` each category profile already carries.
- Every `structured_signals` entry declares which input(s) produced it via `source`; `signal_type: "cross_category_pattern"` is used only when both a category profile and the basket profile independently support the same claim.
- No entry in `structured_signals` carries a numeric score, weight, or rank. `confidence` is the only enum describing how well-evidenced a signal is.
- Discovery and cart-recovery signals describe unmet interest, never grounds to suppress a category.
- Replenishment cadence is a stable trait ("this category moves quickly"); whether a specific item is due right now is a today-specific fact computed from cadence and the last known purchase date — that computation, and the resulting ranking, belongs to the Feed Service at request time, not to this profile.

### 8.3 What this profile hands to the Feed Service, and what it doesn't

The global profile is the stable prior. At request time, the Feed Service:

- joins each `structured_signals` entry back to the deterministic numeric evidence it already computed (cadence days, lift/support numbers, funnel conversion rates) — the same numbers it supplied as input to Pipelines A and B in the first place;
- applies real-time context: inventory, serviceability, current daypart, active missions, and any active occasion-event profile;
- produces the actual weighted, ranked feed.

Cold-start handling follows the same principle: whether a user has enough history to trust this profile is a threshold over order counts and history span the Feed Service already holds. It is not a field this contract asks the LLM to produce.

## 9. Active-occasion overlay contract

Input contract supplied to a later mission-generation step, keeping stable and occasion-specific evidence separate:

```json
{
  "current_context": {"daypart": "evening", "day_type": "weekend", "active_occasion_type": "cricket_match"},
  "user_global_profile": {"profile_text": "...", "mission_generation_text": "...", "overall_confidence": "high"},
  "user_occasion_event_profile": {"occasion_type": "cricket_match", "profile_text": "...", "mission_generation_text": "...", "overall_confidence": "medium"}
}
```

If no matching occasion-event profile exists, `user_occasion_event_profile` is null. A generic occasion understanding may still inform mission generation, but it must not be presented as a learned user preference.

## 10. Numeric evidence the calling service must supply

The LLM never computes counts, cadence, lift, or conversion rates — it only interprets numbers handed to it. The calling service is responsible for computing and supplying:

- **From order history**: category affinity/frequency, median inter-purchase interval and its coefficient of variation (`observed_cadence_days`, `cadence_class`), brand share within category, basket category/product-pair support/confidence/lift, bulk-buying indicators, daypart/day-type share versus the population baseline.
- **From funnel telemetry** (search, product-page view, add-to-cart, remove-from-cart): view-to-cart rate, cart-to-purchase rate, search-to-purchase rate, cart abandonment rate and recency, an unmet-interest count (searches/views/cart-adds with zero purchases), session counts, and the literal high-signal search phrases worth remembering.
- **Explicitly out of scope** until further data exists: true price/discount/value-tier signals (no price feed exists), authoritative mission-to-product mapping (requires a stable catalog join), and any demographic, health, or lifestyle attribute — a policy exclusion, not a data gap.

## 11. Feed usage mapping

| Profile field | Feed surface |
| --- | --- |
| `category_profile.replenishment` | Replenishment-cadence facts; joined with real-time inventory/last-purchase-date by the Feed Service to decide what's due now |
| `category_profile.discovery_candidate` | Discovery / "you might like" module |
| `basket_profile.abandonment_patterns` | Cart-recovery module |
| `basket_profile.category_combination_patterns` | "Did you forget" / basket-completion module |
| `global_profile.replenishment_summary_text` | Cross-category prioritization for module selection |
| `global_profile.structured_signals` | Typed index the Feed Service scores against at request time |
| `user_occasion_event_profile` | Occasion-specific mission boost, applied only while the occasion is active |

## 12. Contract acceptance criteria

- Each category call uses exactly one actual Minutes category, and can represent that category from funnel evidence alone, with zero completed orders.
- A view, search, cart-add, and purchase are never narrated with equivalent certainty language.
- "Stable"/"repeated"/"routine" wording requires repetition across independent dates, gated by the category's supplied cadence.
- Every claim carries `evidence_count`/`independent_date_count` alongside its confidence enum.
- `replenishment.cadence_days`/`cadence_class` are always echoed from supplied input, never computed or guessed by the LLM.
- The global profile's input is exactly the category profiles and the basket-context profile; no other profile feeds it directly.
- `global_profile.replenishment_summary_text` and `category_preference_text` represent every supplied category, not only the strongest.
- `structured_signals` entries declare their source input(s) and carry no numeric score — scoring and ranking are the Feed Service's responsibility, not this contract's.
- Occasion-event behavior remains an overlay and cannot silently rewrite the stable global profile.
- Missing evidence produces null, an empty list, or explicit uncertainty text; it never produces an invented preference, count, or score.
