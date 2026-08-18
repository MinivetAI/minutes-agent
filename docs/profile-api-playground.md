# Minutes Profile API Playground

The local Minutes Agent profile API is available at:

```text
http://127.0.0.1:8091
```

Interactive Swagger UI: <http://127.0.0.1:8091/docs>  
Postman import URL: <http://127.0.0.1:8091/openapi.json>

The API calls the configured Qwen model. It does not create embeddings. The
caller saves the returned text and pre-computes only the embeddings the feed
will consume.

## One summary field

Every category summary contains its commercial facts in a final labelled
clause. There is no separate commercial field:

```json
"summary_text": "Repeatedly buys Amul toned milk in 500 ml packs. Commercial preference: brand_category=national; brand_tier=mass_premium; price_tier=mid"
```

The clause is not embedded as a retrieval query. If catalog input lacks a
value, the API uses `not_observed`, rather than guessing from a brand name.

## User category waterfall

Run these requests in order. Use each response in the next request.

### 1. Daypart category summary

```bash
curl -sS -X POST http://127.0.0.1:8091/user/category/daypart-summary \
  -H 'Content-Type: application/json' \
  -d '{
    "category": "Milk",
    "daypart": "evening",
    "day_type": "weekday",
    "products": [{
      "product_name": "Amul Taaza Pasteurised Toned Milk 500 ml",
      "brand": "Amul",
      "type": "Toned Milk",
      "brand_category": "national",
      "brand_tier": "mass_premium",
      "price_tier": "mid",
      "pack_size": "500 ml",
      "ordered_quantity": 2,
      "product_description": "Pasteurised toned milk."
    }]
  }'
```

### 2. Daily category summary

```bash
curl -sS -X POST http://127.0.0.1:8091/user/category/daily-summary \
  -H 'Content-Type: application/json' \
  -d '{
    "category": "Milk",
    "day_type": "weekday",
    "daypart_summaries": [{
      "daypart": "evening",
      "day_type": "weekday",
      "summary_text": "Observed purchase of 2 units of Amul Taaza Pasteurised Toned Milk (500 ml). Commercial preference: brand_category=national; brand_tier=mass_premium; price_tier=mid"
    }]
  }'
```

### 3. Monthly category summary

```bash
curl -sS -X POST http://127.0.0.1:8091/user/category/monthly-summary \
  -H 'Content-Type: application/json' \
  -d '{
    "category": "Milk",
    "daily_summaries": [{
      "day_type": "weekday",
      "summary_text": "Weekday evening Milk activity contains two 500 ml Amul Taaza toned milk packs. Commercial preference: brand_category=national; brand_tier=mass_premium; price_tier=mid"
    }]
  }'
```

### 4. Final category profile

```bash
curl -sS -X POST http://127.0.0.1:8091/user/category/preference-profile \
  -H 'Content-Type: application/json' \
  -d '{
    "category": "Milk",
    "recent_daypart_summaries": [{
      "daypart": "evening",
      "day_type": "weekday",
      "summary_text": "Observed purchase of 2 units of Amul Taaza Pasteurised Toned Milk (500 ml). Commercial preference: brand_category=national; brand_tier=mass_premium; price_tier=mid"
    }],
    "recent_daily_summaries": [{
      "day_type": "weekday",
      "summary_text": "Weekday evening Milk activity contains two 500 ml Amul Taaza toned milk packs. Commercial preference: brand_category=national; brand_tier=mass_premium; price_tier=mid"
    }],
    "monthly_summaries": [{
      "summary_text": "Milk activity contains two 500 ml Amul Taaza toned milk packs. Commercial preference: brand_category=national; brand_tier=mass_premium; price_tier=mid"
    }]
  }'
```

### 5. User global profile

Use final category summaries plus the final basket summary. Do not pass any
daypart summaries to this call.

```bash
curl -sS -X POST http://127.0.0.1:8091/user/global-profile \
  -H 'Content-Type: application/json' \
  -d '{
    "category_profiles": [{
      "category": "Milk",
      "summary_text": "Repeatedly purchases two 500 ml Amul Taaza toned milk packs. Commercial preference: brand_category=national; brand_tier=mass_premium; price_tier=mid"
    }],
    "basket_summary_text": "Milk commonly appears with everyday biscuits. Commercial preference: brand_category=national; brand_tier=mass_premium; price_tier=mid"
  }'
```

The global response uses both final category and basket summaries for
tangential queries and for the runtime-ready commercial fields:

```json
{
  "brand_category": "national",
  "brand_tier": "mass_premium",
  "price_tier": "mid"
}
```

## Remaining enabled endpoints

| Flow | Endpoints |
| --- | --- |
| User basket | `POST /user/basket/daypart-summary`, `POST /user/basket/daily-summary`, `POST /user/basket/monthly-summary`, `POST /user/basket/profile` |
| Location category | `POST /location/category/daypart-summary`, `POST /location/category/daily-summary`, `POST /location/category/monthly-summary`, `POST /location/category/profile` |
| Location global | `POST /location/global-profile` |

Swagger exposes the exact current request and response schema for every one of
these endpoints. Basket daypart input accepts `daypart`, `day_type`, and an
array of complete `orders`; each order contains its `products` including the
analytical `category`. Location-category daypart input matches user-category
input, with required `order_count` and `buyer_count` for every product.

## Health check

```bash
curl -sS http://127.0.0.1:8091/health
```

It lists the enabled endpoints plus the prompt and schema fingerprints of the
running service.
