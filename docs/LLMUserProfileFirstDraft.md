Minutes Multi-Pipeline LLM User Profile Contract
Status: proposed contract for team review
Date: 2026-07-21
Scope: LLM inputs and outputs only
1. Decision
Build the Minutes user understanding with three independent evidence pipelines:

user × category evidence

  -> daypart category summary

  -> daily category summary

  -> monthly category summary

  -> user category profile

user × complete orders

  -> daypart basket summary

  -> daily basket summary

  -> monthly basket summary

  -> user basket-context profile

user × event evidence

  -> event occurrence summary

  -> user event profile

The stable global profile is produced from category profiles and the basket-context profile:

user category profiles[] + user basket-context profile

  -> user global profile

An event profile is not permanently merged into the global profile. When a relevant event is active, it is supplied as a separate overlay:

user global profile + matching user event profile + current context

  -> personalized mission-generation input

This separation gives the system three different kinds of understanding:

Profile
Primary question
Category profile
What does the user prefer inside this category?
Basket-context profile
What need is the user solving, and how do they construct orders in different circumstances?
Event profile
How does the user's behavior change during a particular event?
Global profile
What stable cross-category and cross-circumstance understanding can be safely retained?

2. Scope boundaries
This document defines:

the unit represented by each LLM call;
the JSON input supplied to the LLM;
the JSON output returned by the LLM;
the output passed into the next LLM stage;
evidence, confidence, and inference rules.

This document does not define Spark implementation, storage technology, serving keys, embeddings, ranking weights, scheduling, retention, or online service integration.
3. Canonical Minutes language
3.1 Dayparts
New profile outputs must use these canonical serving values:

Daypart
Local time
morning
05:00-10:59
afternoon
11:00-15:59
evening
16:00-20:59
night
21:00-04:59


Historical late_night values must be normalized to night before the LLM call. unknown or anytime may be used during ingestion fallback, but must not be emitted as a stable learned daypart preference.
3.2 Categories and missions
category means the product's actual Minutes analyticalVertical, for example Milk, Fruits, Vegetables, or OtherPulses.
analyticalType means the more specific analyticalXtype when available.
No generic FOOD category is introduced by this contract.
Mission evidence must use active Minutes mission_id and description values joined from the active mission catalog.
A mission attached to a product is supporting context. It is not proof that the mission motivated the order.
3.3 Shared enums
{

  "daypart": ["morning", "afternoon", "evening", "night"],

  "day_type": ["weekday", "weekend"],

  "confidence": ["low", "medium", "high"],

  "trend": ["stable", "emerging", "reinforced", "declining"],

  "event_relationship": ["unrelated", "possibly_related", "likely_related"]

}
3.4 Shared LLM rules
Every profile-generation prompt must enforce the following:

Use only supplied products, catalog attributes, mission descriptions, summaries, and context labels.
Never invent categories, brands, pack sizes, quantities, missions, prices, events, or behavioral counts.
Preserve structured evidence references for every material claim.
Separate observed behavior from interpretation.
Treat one occurrence as weak evidence unless the action itself is explicit.
An impression or mission exposure is not a preference. A skipped impression is not automatically a dislike.
If a required attribute is absent, return an empty list or null; do not infer it from general world knowledge.
Do not infer protected, demographic, medical, financial, or psychological characteristics. Describe shopping behavior, not personal identity.
Return only schema-valid JSON.
The next aggregation stage receives the complete structured child outputs, not only their prose paragraphs.

Confidence describes evidence quality:

low: isolated, indirect, ambiguous, or contradictory evidence;
medium: one clear occurrence or a small number of consistent occurrences;
high: repeated, consistent evidence across independent days or event occurrences.

The pipeline should pass deterministic counts into the LLM. The LLM explains their meaning; it must not calculate or invent those counts.

Every request and child profile must also carry an opaque artifact_id assigned by orchestration. The LLM copies this id and uses supplied child ids in evidence references; it never creates identifiers itself.
4. Pipeline A: user category profile
4.1 Flow and responsibility
user × analyticalVertical × daypart × date

  -> DaypartCategorySummary

DaypartCategorySummary[] for one date and category

  -> DailyCategorySummary

DailyCategorySummary[] for one month and category

  -> MonthlyCategorySummary

MonthlyCategorySummary[] for one category

  -> UserCategoryProfile

The final category profile owns brand, product family, variant, pack-size, ordered-quantity, price/value, substitution, replenishment, and temporal preferences inside one category. It does not own cross-category basket intent.
4.2 Daypart category summary
One LLM call represents one user, category, date, and daypart. User and date can remain orchestration metadata; the LLM needs the category, temporal context, and bounded product evidence.

Input:

{

  "artifact_id": "category:Milk:2026-07-21:morning",

  "category": "Milk",

  "temporal_context": {

    "daypart": "morning",

    "day_type": "weekday"

  },

  "evidence_totals": {

    "order_count": 2,

    "product_line_count": 3,

    "ordered_unit_count": 4

  },

  "product_evidence": [

    {

      "evidence_id": "order-101:line-1",

      "product_id": "MLKFG9T8CBZD8G9G",

      "product_name": "Nandini Good Life Toned Milk 500 ml",

      "brand": "Nandini",

      "analytical_type": "MilkXToned",

      "pack_size_text": "500 ml",

      "ordered_quantity": 2,

      "product_description": null,

      "missions": [

        {

          "mission_id": "Quick Breakfast Prep",

          "description": "Breakfast-enabling products for an immediate morning routine."

        },

        {

          "mission_id": "Morning Masala Chai",

          "description": "Products used to prepare masala chai in the morning."

        }

      ]

    }

  ]

}

brand, analytical_type, pack_size_text, and product_description are nullable. A downstream preference about one of these dimensions is allowed only when the corresponding source field is present.

Output:

{

  "artifact_id": "category:Milk:2026-07-21:morning",

  "stage": "daypart_category_summary",

  "category": "Milk",

  "temporal_context": {

    "daypart": "morning",

    "day_type": "weekday"

  },

  "observation_text": "The user ordered toned milk in a 500 ml pack during the weekday morning window.",

  "interpretation_text": "The order is compatible with breakfast or morning beverage preparation, but one day is not enough to establish a durable category preference.",

  "preference_claims": [

    {

      "dimension": "variant",

      "value": "toned milk",

      "claim_text": "Toned milk was selected in this morning window.",

      "confidence": "medium",

      "evidence_ids": ["order-101:line-1"]

    },

    {

      "dimension": "pack_size",

      "value": "500 ml",

      "claim_text": "A 500 ml pack was selected, but repeat evidence is required before calling it a preference.",

      "confidence": "low",

      "evidence_ids": ["order-101:line-1"]

    }

  ],

  "mission_context_text": "Breakfast preparation and morning chai are plausible contexts attached to the product, not confirmed user intent.",

  "uncertainty_text": "There is not yet enough independent evidence to infer stable brand, pack-size, or replenishment behavior.",

  "overall_confidence": "medium"

}
4.3 Daily category summary
One LLM call aggregates all available daypart summaries for the same category and date. It must preserve each daypart rather than flattening them.

Input:

{

  "artifact_id": "category:Milk:2026-07-21:daily",

  "category": "Milk",

  "day_type": "weekday",

  "daypart_summaries": [

    {

      "artifact_id": "category:Milk:2026-07-21:morning",

      "stage": "daypart_category_summary",

      "category": "Milk",

      "temporal_context": {

        "daypart": "morning",

        "day_type": "weekday"

      },

      "observation_text": "The user ordered toned milk in a 500 ml pack during the weekday morning window.",

      "interpretation_text": "The order is compatible with breakfast or morning beverage preparation.",

      "preference_claims": [],

      "mission_context_text": "Breakfast preparation is a plausible context.",

      "uncertainty_text": "This is one day of evidence.",

      "overall_confidence": "medium"

    }

  ]

}

Output:

{

  "artifact_id": "category:Milk:2026-07-21:daily",

  "stage": "daily_category_summary",

  "category": "Milk",

  "day_type": "weekday",

  "summary_text": "Milk activity on this day was concentrated in the morning and involved toned milk in a practical small pack.",

  "daypart_patterns": [

    {

      "daypart": "morning",

      "pattern_text": "Morning activity was compatible with breakfast or beverage preparation.",

      "confidence": "medium",

      "evidence_refs": ["category:Milk:2026-07-21:morning"]

    }

  ],

  "preference_claims": [],

  "cross_daypart_text": "No cross-daypart comparison is possible from the available evidence.",

  "uncertainty_text": "Daily evidence must not be treated as a stable category preference.",

  "overall_confidence": "medium"

}
4.4 Monthly category summary
One LLM call aggregates the daily summaries for one category and month.

Input:

{

  "artifact_id": "category:Milk:2026-07:monthly",

  "category": "Milk",

  "daily_summaries": [

    {

      "artifact_id": "category:Milk:2026-07-21:daily",

      "stage": "daily_category_summary",

      "category": "Milk",

      "day_type": "weekday",

      "summary_text": "Milk activity was concentrated in the morning.",

      "daypart_patterns": [

        {

          "daypart": "morning",

          "pattern_text": "The user selected toned milk in practical small packs.",

          "confidence": "medium",

          "evidence_refs": ["category:Milk:2026-07-21:morning"]

        }

      ],

      "preference_claims": [],

      "cross_daypart_text": "Morning is the strongest observed daypart.",

      "uncertainty_text": "Other dayparts have limited evidence.",

      "overall_confidence": "medium"

    }

  ]

}

Output:

{

  "artifact_id": "category:Milk:2026-07:monthly",

  "stage": "monthly_category_summary",

  "category": "Milk",

  "summary_text": "Across the month, Milk purchases repeatedly supported weekday morning routines, with recurring selection of toned milk and smaller practical packs.",

  "stable_preference_claims": [

    {

      "dimension": "variant",

      "value": "toned milk",

      "claim_text": "Toned milk is the most consistently observed Milk variant.",

      "confidence": "high",

      "evidence_refs": ["category:Milk:2026-07-21:daily"]

    }

  ],

  "temporal_patterns": [

    {

      "daypart": "morning",

      "day_type": "weekday",

      "pattern_text": "Milk demand is strongest during weekday mornings.",

      "confidence": "high",

      "evidence_refs": ["category:Milk:2026-07-21:daily"]

    }

  ],

  "trend_claims": [],

  "uncertainty_text": "Brand preference remains weaker than the observed variant and temporal preference.",

  "overall_confidence": "high"

}
4.5 User category profile
One LLM call produces the durable profile for one user and one actual Minutes category from the available monthly summaries.

Input:

{

  "artifact_id": "category:Milk:profile",

  "category": "Milk",

  "monthly_summaries": [

    {

      "artifact_id": "category:Milk:2026-07:monthly",

      "stage": "monthly_category_summary",

      "category": "Milk",

      "summary_text": "Milk purchases repeatedly supported weekday morning routines.",

      "stable_preference_claims": [],

      "temporal_patterns": [],

      "trend_claims": [],

      "uncertainty_text": "Brand evidence is still limited.",

      "overall_confidence": "high"

    }

  ]

}

Output:

{

  "artifact_id": "category:Milk:profile",

  "stage": "user_category_profile",

  "category": "Milk",

  "profile_text": "The user treats Milk as a routine household-continuity category, with the strongest demand during weekday mornings. Toned milk and practical small packs are the most consistent observed choices.",

  "brand_preferences": [{
      "brand": "Nandini",
      "preferenceText": "Most consistently selected milk brand.",
      "confidence": "high"
    }
],

  "product_preferences": [

    {

      "value": "toned milk",

      "preference_text": "Toned milk is the most consistently selected variant.",

      "confidence": "high",

      "evidence_refs": ["category:Milk:2026-07:monthly"]

    }

  ],

  "quantity_preferences": [

    {

      "value": "small practical packs",

      "preference_text": "Smaller packs are repeatedly selected for routine use.",

      "confidence": "medium",

      "evidence_refs": ["category:Milk:2026-07:monthly"]

    }

  ],

  "temporal_preferences": [

    {

      "daypart": "morning",

      "day_type": "weekday",

      "preference_text": "Milk demand is strongest during weekday morning routines.",

      "confidence": "high",

      "evidence_refs": ["category:Milk:2026-07:monthly"]

    }

  ],

  "replenishment_text": "Behavior is more consistent with repeat replenishment than broad category exploration.",

  "substitution_text": null,

  "price_value_text": null,

  "emerging_preferences": [],

  "avoidance_or_uncertainty_text": "No durable brand, price, or substitution preference is asserted without additional evidence.",

  "mission_generation_text": "Prefer familiar morning milk replenishment and breakfast-support missions while preserving variant and pack-size preferences.",

  "overall_confidence": "high"

}
5. Pipeline B: user basket-context profile
5.1 Flow and responsibility
complete orders for user × date × daypart

  -> DaypartBasketSummary

DaypartBasketSummary[] for one date

  -> DailyBasketSummary

DailyBasketSummary[] for one month

  -> MonthlyBasketSummary

MonthlyBasketSummary[]

  -> UserBasketContextProfile

The basket pipeline owns need states, category combinations, replenishment versus urgency, order-building behavior, repeated missions, daypart behavior, and circumstance-dependent shopping modes. Product lines from the same order must remain together.
5.2 Daypart basket summary
Input:

{

  "artifact_id": "basket:2026-07-21:morning",

  "temporal_context": {

    "daypart": "morning",

    "day_type": "weekday"

  },

  "orders": [

    {

      "order_id": "order-101",

      "items": [

        {

          "product_id": "MLKFG9T8CBZD8G9G",

          "product_name": "Nandini Good Life Toned Milk 500 ml",

          "category": "Milk",

          "ordered_quantity": 2,

          "missions": [

            {

              "mission_id": "Quick Breakfast Prep",

              "description": "Breakfast-enabling products for an immediate morning routine."

            }

          ]

        },

        {

          "product_id": "FRTFFHGPZJGCG83D",

          "product_name": "Grapes Green Seedless 500 g",

          "category": "Fruits",

          "ordered_quantity": 1,

          "missions": [

            {

              "mission_id": "Fruit",

              "description": "Fresh fruit purchasing for immediate consumption or household use."

            }

          ]

        }

      ]

    }

  ],

  "event_context": null

}

Output:

{

  "artifact_id": "basket:2026-07-21:morning",

  "stage": "daypart_basket_summary",

  "temporal_context": {

    "daypart": "morning",

    "day_type": "weekday"

  },

  "basket_summary_text": "The morning order combines milk and fresh fruit, consistent with immediate breakfast support or routine household replenishment.",

  "need_state_claims": [

    {

      "need_state": "morning_routine_support",

      "claim_text": "The basket supports an immediate morning consumption routine.",

      "confidence": "medium",

      "evidence_order_ids": ["order-101"]

    }

  ],

  "shopping_mode_claims": [

    {

      "mode": "routine_replenishment",

      "claim_text": "The basket is compatible with replenishing familiar everyday products.",

      "confidence": "low",

      "evidence_order_ids": ["order-101"]

    }

  ],

  "category_combinations": [

    {

      "categories": ["Milk", "Fruits"],

      "combination_text": "Milk and fresh fruit were purchased together for a likely morning-use occasion.",

      "confidence": "medium",

      "evidence_order_ids": ["order-101"]

    }

  ],

  "mission_signals": [

    {

      "mission_id": "Quick Breakfast Prep",

      "signal_text": "The order is compatible with quick breakfast preparation.",

      "confidence": "medium",

      "evidence_order_ids": ["order-101"]

    }

  ],

  "event_relationship": null,

  "uncertainty_text": "One basket is insufficient to establish a recurring shopping mode.",

  "overall_confidence": "medium"

}

If authoritative event_context is present, the output may populate event_relationship. The LLM must still decide whether the basket contents are actually related to the event.
5.3 Daily basket summary
Input:

{

  "artifact_id": "basket:2026-07-21:daily",

  "day_type": "weekday",

  "daypart_basket_summaries": [

    {

      "artifact_id": "basket:2026-07-21:morning",

      "stage": "daypart_basket_summary",

      "temporal_context": {

        "daypart": "morning",

        "day_type": "weekday"

      },

      "basket_summary_text": "The morning order supported breakfast or household continuity.",

      "need_state_claims": [],

      "shopping_mode_claims": [],

      "category_combinations": [],

      "mission_signals": [],

      "event_relationship": null,

      "uncertainty_text": "One morning basket is available.",

      "overall_confidence": "medium"

    }

  ]

}

Output:

{

  "artifact_id": "basket:2026-07-21:daily",

  "stage": "daily_basket_summary",

  "day_type": "weekday",

  "summary_text": "The day's observed order activity was concentrated in the morning and supported immediate household consumption.",

  "daypart_behavior": [

    {

      "daypart": "morning",

      "behavior_text": "The user constructed a small practical basket around morning-use products.",

      "confidence": "medium",

      "evidence_refs": ["basket:2026-07-21:morning"]

    }

  ],

  "need_state_patterns": [],

  "shopping_mode_patterns": [],

  "category_combination_patterns": [],

  "mission_patterns": [],

  "event_specific_patterns": [],

  "uncertainty_text": "No cross-day recurrence can be inferred at the daily stage.",

  "overall_confidence": "medium"

}
5.4 Monthly basket summary
Input:

{

  "artifact_id": "basket:2026-07:monthly",

  "daily_basket_summaries": [

    {

      "artifact_id": "basket:2026-07-21:daily",

      "stage": "daily_basket_summary",

      "day_type": "weekday",

      "summary_text": "Morning ordering supported immediate household consumption.",

      "daypart_behavior": [],

      "need_state_patterns": [],

      "shopping_mode_patterns": [],

      "category_combination_patterns": [],

      "mission_patterns": [],

      "event_specific_patterns": [],

      "uncertainty_text": "Other dayparts have limited evidence.",

      "overall_confidence": "medium"

    }

  ]

}

Output:

{

  "artifact_id": "basket:2026-07:monthly",

  "stage": "monthly_basket_summary",

  "summary_text": "Across the month, the user most often used Minutes for routine household continuity, with morning baskets supporting immediate consumption and evening baskets completing cooking needs.",

  "stable_daypart_behavior": [

    {

      "daypart": "morning",

      "day_type": "weekday",

      "behavior_text": "Morning baskets repeatedly support breakfast and everyday household continuity.",

      "confidence": "high",

      "evidence_refs": ["basket:2026-07-21:daily"]

    }

  ],

  "stable_need_states": [

    {

      "need_state": "household_continuity",

      "pattern_text": "The user repeatedly restores familiar everyday products.",

      "confidence": "high",

      "evidence_refs": ["basket:2026-07-21:daily"]

    }

  ],

  "stable_shopping_modes": [

    {

      "mode": "routine_replenishment",

      "pattern_text": "Repeat baskets are more common than broad discovery baskets.",

      "confidence": "high",

      "evidence_refs": ["basket:2026-07-21:daily"]

    }

  ],

  "category_combination_patterns": [],

  "mission_patterns": [],

  "event_specific_patterns": [],

  "trend_claims": [],

  "overall_confidence": "high"

}

Event-specific patterns remain explicitly separated. They may be forwarded to the event pipeline but must not dominate the stable basket profile.
5.5 User basket-context profile
Input:

{

  "artifact_id": "basket:profile",

  "monthly_basket_summaries": [

    {

      "artifact_id": "basket:2026-07:monthly",

      "stage": "monthly_basket_summary",

      "summary_text": "The user most often used Minutes for routine household continuity.",

      "stable_daypart_behavior": [],

      "stable_need_states": [],

      "stable_shopping_modes": [],

      "category_combination_patterns": [],

      "mission_patterns": [],

      "event_specific_patterns": [],

      "trend_claims": [],

      "overall_confidence": "high"

    }

  ]

}

Output:

{

  "artifact_id": "basket:profile",

  "stage": "user_basket_context_profile",

  "profile_text": "The user primarily uses Minutes for practical household continuity and immediate need completion. Weekday mornings support routine consumption, while evening orders are more likely to close cooking or household gaps.",

  "behaviour_pattern": [

    {

      "behavior_text": "The user repeatedly restores familiar everyday products.",

      "confidence": "high",

      "evidence_refs": ["basket:2026-07:monthly"]

    }

  ],

  "daypart_behavior": [

    {

      "daypart": "morning",

      "day_type": "weekday",

      "behavior_text": "Morning baskets are oriented toward breakfast and everyday household continuity.",

      "confidence": "high",

      "evidence_refs": ["basket:2026-07:monthly"]

    }

  ],

  "basket_structure_text": "Observed baskets are generally practical and need-completing rather than broad discovery baskets.",

  "circumstance_patterns": [

    {

      "circumstance": "household_stockout_or_replenishment",

      "behavior_text": "The user uses quick commerce to restore missing everyday products.",

      "confidence": "medium",

      "evidence_refs": ["basket:2026-07:monthly"]

    }

  ],

  "category_combination_patterns": [],

  "mission_patterns": [],

  "mission_generation_text": "Prioritize replenishment, breakfast continuity, cooking-gap completion, and immediate household rescue missions when supported by the current context.",

  "avoidance_or_uncertainty_text": "The profile describes observed shopping modes and does not assert a fixed personality or demographic identity.",

  "overall_confidence": "high"

}
6. Pipeline C: user event profile
6.1 Flow and responsibility
Events use their natural occurrence boundary rather than the normal daypart-to-daily-to-monthly waterfall:

event-labelled basket summaries for one occurrence

  -> EventOccurrenceSummary

EventOccurrenceSummary[] for one event type

  -> UserEventProfile

Authoritative event identity must be supplied by the calling system. The LLM may assess whether an order is related to the event, but it must not invent an active event from product behavior alone.
6.2 Event occurrence summary
Input:

{

  "artifact_id": "event:cricket-match-2026-07-21:occurrence",

  "event_context": {

    "event_id": "cricket-match-2026-07-21",

    "event_type": "cricket_match",

    "event_name": "Cricket match"

  },

  "basket_summaries": [

    {

      "daypart": "evening",

      "basket_summary_text": "The order combined ready-to-consume snacks and chilled beverages.",

      "event_relationship": "likely_related",

      "evidence_order_ids": ["order-701"]

    }

  ],

  "ordinary_baseline_text": "Ordinary evening baskets are more often focused on cooking staples and household replenishment."

}

Output:

{

  "artifact_id": "event:cricket-match-2026-07-21:occurrence",

  "stage": "event_occurrence_summary",

  "event_type": "cricket_match",

  "event_name": "Cricket match",

  "occurrence_summary_text": "During this match, the user shifted toward ready-to-consume snacks and chilled beverages in the evening.",

  "behavior_delta_text": "The basket differed from the user's ordinary cooking- and replenishment-led evening behavior.",

  "daypart_behavior": [

    {

      "daypart": "evening",

      "behavior_text": "Event-related purchasing occurred during the evening viewing window.",

      "confidence": "medium",

      "evidence_order_ids": ["order-701"]

    }

  ],

  "category_shifts": [

    {

      "category": "Chips",

      "shift_text": "Ready-to-consume snack demand appeared stronger than in the ordinary baseline.",

      "confidence": "medium",

      "evidence_order_ids": ["order-701"]

    }

  ],

  "mission_signals": [],

  "uncertainty_text": "One event occurrence is insufficient to establish a persistent matchday preference.",

  "overall_confidence": "medium"

}
6.3 User event profile
Input:

{

  "artifact_id": "event:cricket_match:profile",

  "event_type": "cricket_match",

  "occurrence_summaries": [

    {

      "artifact_id": "event:cricket-match-2026-07-21:occurrence",

      "stage": "event_occurrence_summary",

      "event_type": "cricket_match",

      "event_name": "Cricket match",

      "occurrence_summary_text": "The user shifted toward snacks and chilled beverages.",

      "behavior_delta_text": "This differed from ordinary evening behavior.",

      "daypart_behavior": [],

      "category_shifts": [],

      "mission_signals": [],

      "uncertainty_text": "One occurrence is available.",

      "overall_confidence": "medium"

    }

  ],

  "ordinary_basket_profile_text": "The user normally uses evening orders for cooking completion and household replenishment."

}

Output:

{

  "artifact_id": "event:cricket_match:profile",

  "stage": "user_event_profile",

  "event_type": "cricket_match",

  "profile_text": "During cricket matches, the user tends to shift from ordinary cooking and replenishment baskets toward immediately consumable snacks and beverages.",

  "behavior_delta_text": "Match contexts increase entertainment-oriented convenience purchasing relative to the user's ordinary evening baseline.",

  "preferred_dayparts": [

    {

      "daypart": "evening",

      "preference_text": "Match-related purchasing is strongest during evening viewing windows.",

      "confidence": "medium",

      "evidence_refs": ["event:cricket-match-2026-07-21:occurrence"]

    }

  ],

  "category_signals": [

    {

      "category": "Chips",

      "preference_text": "Ready-to-consume snacks become more relevant during match contexts.",

      "confidence": "medium",

      "evidence_refs": ["event:cricket-match-2026-07-21:occurrence"]

    }

  ],

  "basket_patterns": [],

  "mission_patterns": [],

  "mission_generation_text": "When a cricket match is active, consider match-viewing snack, chilled beverage, and quick sharing missions without replacing the user's stable preferences.",

  "uncertainty_text": "Apply this profile only when the matching event is active and supported by sufficient occurrence evidence.",

  "overall_confidence": "medium"

}

If there is no meaningful evidence for a user and event type, a user event profile should not be created. The downstream system may use a generic event understanding, clearly separated from learned user behavior.
7. User global profile
The global profile synthesizes stable category and basket-context understanding. It does not absorb event-specific behavior.

Input:

{

  "artifact_id": "global:profile",

  "category_profiles": [

    {

      "artifact_id": "category:Milk:profile",

      "category": "Milk",

      "profile_text": "The user treats Milk as a routine morning household-continuity category.",

      "mission_generation_text": "Prefer familiar morning replenishment and breakfast-support missions.",

      "overall_confidence": "high"

    }

  ],

  "basket_context_profile": {

    "artifact_id": "basket:profile",

    "profile_text": "The user primarily uses Minutes for practical household continuity and immediate need completion.",

    "mission_generation_text": "Prioritize replenishment and immediate household rescue when contextually relevant.",

    "overall_confidence": "high"

  }

}

Output:

{

  "artifact_id": "global:profile",

  "stage": "user_global_profile",

  "profile_text": "The user is a routine-oriented quick-commerce shopper who primarily uses Minutes for household continuity and immediate need completion. Stable category choices favor familiar, practical products, while the applicable mission changes with daypart and basket circumstance.",

  "category_preference_text": "Frequently used categories show practical variant and pack-size choices, with stronger confidence in repeated morning routines.",

  "basket_context_text": "The user usually builds need-completing baskets rather than broad discovery baskets.",

  "cross_category_patterns": [

    {

      "pattern_text": "Morning category preferences and basket behavior jointly support breakfast and household-continuity needs.",

      "confidence": "high",

      "evidence_refs": ["category:Milk:profile", "basket:profile"]

    }

  ],

  "stable_mission_tendencies": [

    {

      "tendency_text": "Routine replenishment and immediate need completion are the strongest stable mission families.",

      "confidence": "high",

      "evidence_refs": ["category:Milk:profile", "basket:profile"]

    }

  ],

  "mission_generation_text": "Generate missions that preserve trusted category preferences while adapting to the current daypart, observed basket circumstance, and any separately supplied active-event profile.",

  "uncertainty_text": "Do not generalize weak category evidence or event-specific behavior into stable global preferences.",

  "overall_confidence": "high"

}
8. Active-event overlay contract
This is the input contract supplied to a later mission-generation step. It keeps stable and contextual evidence separate instead of generating a new permanent profile.

{

  "artifact_id": "mission-context:2026-07-21:evening",

  "current_context": {

    "daypart": "evening",

    "day_type": "weekend",

    "active_event_type": "cricket_match"

  },

  "user_global_profile": {

    "artifact_id": "global:profile",

    "profile_text": "The user primarily values practical household continuity and immediate need completion.",

    "mission_generation_text": "Preserve familiar category preferences and adapt to the current circumstance.",

    "overall_confidence": "high"

  },

  "user_event_profile": {

    "artifact_id": "event:cricket_match:profile",

    "event_type": "cricket_match",

    "profile_text": "During cricket matches, the user shifts toward immediately consumable snacks and beverages.",

    "mission_generation_text": "Consider match-viewing snack, chilled beverage, and quick sharing missions.",

    "overall_confidence": "medium"

  }

}

If no matching user event profile exists, user_event_profile is null. The generic event context may still inform mission generation, but it must not be presented as a learned user preference.
9. Contract acceptance criteria
The contract is ready for implementation when the team agrees that:

Each category call uses exactly one actual Minutes analyticalVertical.
Complete orders remain intact in the basket pipeline.
Daypart structure survives daily and monthly aggregation.
Brand, quantity, pack-size, price, and substitution claims require explicit source fields and evidence references.
Daily and monthly stages consume structured child outputs, not recursively flattened prose alone.
Event identity comes from an authoritative context source.
Event profiles aggregate event occurrences rather than calendar months.
Event behavior remains an overlay and cannot silently rewrite the stable global profile.
Every material claim includes confidence and evidence references.
Missing evidence produces null, an empty list, or explicit uncertainty; it never produces an invented preference.

