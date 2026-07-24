# Minutes User Profile Tasks

This document describes the current user-profile tasks exposed by
`minutes-agent`.

There are two profile families:

1. Category behavior profiles: older category-level summaries and profiles.
2. Mission profiles: newer mission-based temporal profiles built from product
   orders and product mission ids.

## Task Summary

| Task | Endpoint | Purpose |
| --- | --- | --- |
| `user_hourly_summary` | `POST /user/hourly-summary` | Summarize one hour of activity inside one product category. |
| `user_aggregate_summary` | `POST /user/aggregate-summary` | Aggregate hourly summaries into daily, or daily summaries into monthly. |
| `user_category_profile` | `POST /user/category-profile` | Build one category-level user profile from hourly/daily/monthly summaries. |
| `user_cross_category_profile` | `POST /user/cross-category-profile` | Build one cross-category profile from category profiles. |
| `user_mission_hourly_summary` | `POST /user/mission-hourly-summary` | Summarize mission signals from one temporal order window. |
| `user_mission_aggregate_summary` | `POST /user/mission-aggregate-summary` | Aggregate mission summaries using `granularity = daily` or `monthly`. |
| `user_mission_global_profile` | `POST /user/mission-global-profile` | Build the global temporal mission profile from hourly/daily/monthly mission summaries. |

## Category Profile Flow

The category profile flow is category-first. It works with product descriptions
and aggregate summary text.

```text
raw category activity
  -> /user/hourly-summary
  -> /user/aggregate-summary with granularity=daily
  -> /user/aggregate-summary with granularity=monthly
  -> /user/category-profile
  -> /user/cross-category-profile
```

### Hourly Category Summary

Request:

```json
{
  "category": "Milk",
  "total_interactions": 12,
  "total_purchases": 2,
  "descriptions": [
    "Amul Taaza toned milk 1L for daily tea and breakfast use",
    "Nandini toned milk pouch for household replenishment"
  ]
}
```

Response:

```json
{
  "summary": "User browsed 12 Milk products and purchased 2 items..."
}
```

### Category Aggregate Summary

Use the same endpoint for daily and monthly aggregation.

Daily request:

```json
{
  "category": "Milk",
  "granularity": "daily",
  "total_interactions": 38,
  "total_purchases": 3,
  "summaries": [
    "User browsed daily milk packs in the morning...",
    "User compared toned and full cream milk options..."
  ]
}
```

Monthly request:

```json
{
  "category": "Milk",
  "granularity": "monthly",
  "total_interactions": 420,
  "total_purchases": 28,
  "summaries": [
    "On this day, user showed routine milk replenishment...",
    "On this day, user focused on 1L household milk packs..."
  ]
}
```

Response:

```json
{
  "summary": "During this period, the user shows stable milk replenishment behavior..."
}
```

### Category Profile

Request:

```json
{
  "category": "Milk",
  "hourly_summaries": [
    "User browsed 1L milk packs for breakfast and tea use."
  ],
  "daily_summaries": [],
  "monthly_summaries": [
    "During the month, user repeatedly bought milk for household replenishment."
  ]
}
```

Response:

```json
{
  "profile": "The user has a stable Milk preference tied to routine household replenishment..."
}
```

### Cross-Category Profile

Request:

```json
{
  "category_profiles": [
    {
      "category": "Milk",
      "profile": "The user shows routine household milk replenishment."
    },
    {
      "category": "ReadyMeals",
      "profile": "The user uses ready meals for convenience-led eating."
    }
  ]
}
```

Response:

```json
{
  "profile": "The user is routine-led, with recurring household staples and convenience food behavior..."
}
```

## Mission Profile Flow

The mission profile flow is mission-first. It is built around product orders and
product mission ids. It does not use raw monthly text.

Only these new mission-profile endpoints are current:

```text
POST /user/mission-hourly-summary
POST /user/mission-aggregate-summary
POST /user/mission-global-profile
```

There are no separate mission daily/monthly endpoints. Daily and monthly mission
aggregation both go through `/user/mission-aggregate-summary`; the
`granularity` field decides which aggregation is being requested.

```text
hourly orders with product mission ids
  -> /user/mission-hourly-summary
  -> /user/mission-aggregate-summary with granularity=daily
  -> /user/mission-aggregate-summary with granularity=monthly
  -> /user/mission-global-profile
```

Temporal values are bounded:

```text
daypart:  morning | afternoon | evening | night | unknown
day_type: weekday | weekend | unknown
```

### Mission Hourly Summary

Request:

```json
{
  "temporal_context": {
    "daypart": "morning",
    "day_type": "weekday"
  },
  "orders": [
    {
      "product_name": "Amul Taaza Toned Milk 1L",
      "missions": [
        {
          "mission_id": "daily_breakfast",
          "description": "User needs breakfast-enabling staples for morning routine."
        },
        {
          "mission_id": "tea_preparation",
          "description": "User needs milk or related items to prepare tea."
        }
      ]
    },
    {
      "product_name": "Britannia Bread",
      "missions": [
        {
          "mission_id": "daily_breakfast",
          "description": "User needs breakfast-enabling staples for morning routine."
        }
      ]
    }
  ]
}
```

Response:

```json
{
  "temporal_context": {
    "daypart": "morning",
    "day_type": "weekday"
  },
  "summary": "The user shows a weekday morning breakfast and tea-preparation mission.",
  "mission_signals": [
    {
      "mission_id": "daily_breakfast",
      "confidence": "high",
      "evidence_products": [
        "Amul Taaza Toned Milk 1L",
        "Britannia Bread"
      ]
    },
    {
      "mission_id": "tea_preparation",
      "confidence": "medium",
      "evidence_products": [
        "Amul Taaza Toned Milk 1L"
      ]
    }
  ],
  "dominant_missions": [
    "daily_breakfast"
  ]
}
```

### Mission Aggregate Summary

Daily and monthly mission aggregation use the same endpoint:

```text
POST /user/mission-aggregate-summary
```

Use:

```json
{
  "granularity": "daily",
  "summaries": []
}
```

for hourly-to-daily aggregation.

Use:

```json
{
  "granularity": "monthly",
  "summaries": []
}
```

for daily-to-monthly aggregation.

Daily request:

```json
{
  "granularity": "daily",
  "summaries": [
    {
      "temporal_context": {
        "daypart": "morning",
        "day_type": "weekday"
      },
      "summary": "The user ordered milk and bread for breakfast and tea preparation.",
      "mission_signals": [
        {
          "mission_id": "daily_breakfast",
          "confidence": "high",
          "evidence_products": [
            "Amul Taaza Toned Milk 1L",
            "Britannia Bread"
          ]
        }
      ],
      "dominant_missions": [
        "daily_breakfast"
      ]
    }
  ]
}
```

Daily response:

```json
{
  "summary": "The user's weekday morning behavior is anchored around breakfast preparation.",
  "day_type": "weekday",
  "temporal_mission_patterns": [
    {
      "daypart": "morning",
      "mission_id": "daily_breakfast",
      "confidence": "high",
      "evidence": [
        "milk and bread breakfast order"
      ]
    }
  ],
  "temporal_mission_profile": [],
  "dominant_missions": [
    "daily_breakfast"
  ]
}
```

Monthly request:

```json
{
  "granularity": "monthly",
  "summaries": [
    {
      "summary": "The user's weekday morning behavior is anchored around breakfast preparation.",
      "day_type": "weekday",
      "temporal_mission_patterns": [
        {
          "daypart": "morning",
          "mission_id": "daily_breakfast",
          "confidence": "high",
          "evidence": [
            "milk and bread breakfast order"
          ]
        }
      ],
      "temporal_mission_profile": [],
      "dominant_missions": [
        "daily_breakfast"
      ]
    }
  ]
}
```

Monthly response:

```json
{
  "summary": "The user has a recurring weekday morning breakfast mission.",
  "day_type": null,
  "temporal_mission_patterns": [],
  "temporal_mission_profile": [
    {
      "day_type": "weekday",
      "daypart": "morning",
      "mission_id": "daily_breakfast",
      "frequency": "recurring",
      "confidence": "high",
      "evidence": [
        "repeated weekday morning breakfast summaries"
      ]
    }
  ],
  "dominant_missions": [
    "daily_breakfast"
  ]
}
```

### Mission Global Profile

Request:

```json
{
  "hourlySummaries": [],
  "dailySummaries": [],
  "monthlySummaries": [
    {
      "summary": "The user has a recurring weekday morning breakfast mission.",
      "day_type": null,
      "temporal_mission_patterns": [],
      "temporal_mission_profile": [
        {
          "day_type": "weekday",
          "daypart": "morning",
          "mission_id": "daily_breakfast",
          "frequency": "recurring",
          "confidence": "high",
          "evidence": [
            "repeated weekday morning breakfast summaries"
          ]
        }
      ],
      "dominant_missions": [
        "daily_breakfast"
      ]
    }
  ]
}
```

Response:

```json
{
  "profile": "The user has a stable weekday morning breakfast mission and should be personalized toward breakfast staples in that context.",
  "temporal_mission_profile": [
    {
      "day_type": "weekday",
      "daypart": "morning",
      "mission_id": "daily_breakfast",
      "strength": "primary",
      "frequency": "recurring",
      "confidence": "high",
      "personalization_hint": "Boost breakfast staples and close complements during weekday mornings."
    }
  ],
  "dominant_missions": [
    "daily_breakfast"
  ],
  "recent_mission_shifts": []
}
```

## Inference Task Names

`minutes-inference` currently maps these task names to the mission endpoints:

| Inference task | Agent endpoint |
| --- | --- |
| `llm_user_mission_hourly_summary` | `${minutes.agent.base-url}/user/mission-hourly-summary` |
| `llm_user_mission_aggregate_summary` | `${minutes.agent.base-url}/user/mission-aggregate-summary` |
| `llm_user_mission_global_profile` | `${minutes.agent.base-url}/user/mission-global-profile` |

Set the agent base URL with:

```text
MINUTES_AGENT_BASE_URL=http://localhost:8067
```

or, if inference runs on another host:

```text
MINUTES_AGENT_BASE_URL=http://<minutes-agent-host>:8067
```

## Curl Smoke Tests

List enabled tasks:

```bash
PYTHONPATH=/mnt/data/alfred python3 app.py --list-tasks
```

Start with the mission tasks:

```bash
PYTHONPATH=/mnt/data/alfred python3 app.py \
  --tasks user_mission_hourly_summary,user_mission_aggregate_summary,user_mission_global_profile \
  --vllm-url http://10.116.13.247:9000/v1 \
  --model Qwen35 \
  --host 0.0.0.0 \
  --port 8067 \
  --max-concurrent 256
```

Health checks:

```bash
curl -s http://localhost:8067/health
curl -s http://localhost:8067/
```

## Text-First Feed Profile Waterfall

The recommendation experiment uses these first-class `minutes-agent` tasks.
They are daypart-first; no hourly summary is created for this flow.

| Task | Endpoint |
| --- | --- |
| `user_category_daypart_summary` | `POST /user/category/daypart-summary` |
| `user_category_daily_summary` | `POST /user/category/daily-summary` |
| `user_category_monthly_summary` | `POST /user/category/monthly-summary` |
| `user_category_preference_profile` | `POST /user/category/preference-profile` |
| `user_basket_daypart_summary` | `POST /user/basket/daypart-summary` |
| `user_basket_daily_summary` | `POST /user/basket/daily-summary` |
| `user_basket_monthly_summary` | `POST /user/basket/monthly-summary` |
| `user_basket_profile` | `POST /user/basket/profile` |
| `user_global_profile` | `POST /user/global-profile` |
| `user_feed_quality_review` | `POST /user/feed-quality-review` |

```text
category orders -> category daypart -> daily -> monthly -> category profile
complete orders -> basket daypart   -> daily -> monthly -> basket profile
category profiles + basket profile + recent summaries -> global profile
```

Start the complete task set:

```bash
python app.py \
  --tasks user_category_daypart_summary,user_category_daily_summary,user_category_monthly_summary,user_category_preference_profile,user_basket_daypart_summary,user_basket_daily_summary,user_basket_monthly_summary,user_basket_profile,user_global_profile,user_feed_quality_review \
  --vllm-url http://rtx-1.dev.internal:8040/v1 \
  --model qwen3.6-35b \
  --port 8091
```

Example first-stage request:

```json
{
  "category": "Milk",
  "date": "2026-07-23",
  "daypart": "afternoon",
  "day_type": "weekday",
  "order_count": 1,
  "products": [
    {
      "product_name": "Amul Taaza Pasteurised Toned Milk 500 ml",
      "category": "Milk",
      "product_type": "Toned Milk",
      "quantity": 2,
      "product_paragraph": "Amul Taaza is a 500 ml toned-milk pack for everyday use.",
      "general_product_uses": "Shoppers generally buy it for routine milk replenishment."
    }
  ]
}
```

The agent renderer removes URLs and presents this as readable named evidence
sections. General product uses are explicitly labelled as context, not proof of
the user's intent. Cache keys, artifact ids, input digests, order ids, product
ids, and evidence-reference plumbing are not part of these task contracts.

`GET /health` also returns the endpoint, model, prompt hash, input/output schema
hashes, and combined `definition_sha256` for every enabled task. Consumers
include that combined definition hash in cache keys so model, prompt, or
contract changes invalidate old generations.
