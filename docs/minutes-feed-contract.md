# Minutes Feed Contract

## 1. Scope of this document

This document defines the production feed contract: runtime records, candidate
retrieval, product and mission ranking, importance allocation, diversity,
homepage caching, load more, and mission-detail products. It is not an LLM
input/output or profile-generation contract.

The feed directly consumes embeddings from its runtime records.

## 2. Initial feed request

```json
{
  "userId": "U123",
  "hexIds": ["HEX_456", "HEX_789"],
  "daypart": "evening",
  "dayType": "weekday",
  "eventIds": ["monsoon", "match_day"],
  "pageSize": 12
}
```

| Field | Required | Meaning |
| --- | --- | --- |
| `userId` | Yes | User whose runtime profile records are loaded. |
| `hexIds` | Yes | Hexes where a product may be serviceable. |
| `daypart` | Yes | Caller-provided: `morning`, `afternoon`, `evening`, or `night`. |
| `dayType` | Yes | Caller-provided: `weekday` or `weekend`. |
| `eventIds` | Yes, may be empty | Active contextual IDs, including seasons such as `monsoon`. |
| `pageSize` | No | Requested product count; default is `12`. |

The feed does not derive daypart or day type. It treats a season as an event,
so there is no separate season field.

`hexIds` is a list. Product serviceability behavior across multiple hexes will
be defined in the Solr retrieval section.

## 3. Product runtime metadata

Every feed-eligible product has this runtime metadata:

```json
{
  "productId": "P90210",
  "productName": "Amul Taaza Toned Milk 500 ml",
  "brand": "Amul",
  "analyticalVertical": "Milk",
  "type": "Toned Milk",
  "orderScore": 0.82,
  "freshnessScore": 0.74,
  "brandTier": "mass_premium",
  "priceTier": "mid",
  "brandCategory": "Amul",
  "embedding": []
}
```

| Field | Meaning |
| --- | --- |
| `productId` | Stable product identity. |
| `productName` | Product display name. |
| `brand` | Canonical catalog brand, for example `Amul`; used for final brand spacing. |
| `analyticalVertical` | Product analytical category. |
| `type` | Product type within its analytical vertical. |
| `orderScore` | Product order signal. |
| `freshnessScore` | Product freshness signal. |
| `brandTier` | Brand tier used as a user-preference ranking boost. |
| `priceTier` | Price tier used as a user-preference ranking boost. |
| `brandCategory` | Commercial brand class, for example `d2c`, `cheap`, or `local`. |
| `embedding` | Product semantic vector used by feed retrieval. |

The retrieval, boost, and spacing use of these fields is defined in Sections
12.1, 12.3, and 12.6. This contract has no separate final L2 stage.

## 4. Mission runtime metadata

Every feed-eligible mission has this runtime metadata:

```json
{
  "missionId": "home_garden_prep",
  "missionName": "Home Garden Prep",
  "description": "Prepare and maintain a home garden with soil, potting mix, fertilizer, manure, and related plant-care essentials.",
  "tags": [
    "daypart:all_day",
    "event:summer",
    "event:monsoon",
    "analyticalVertical:SoilManure",
    "analyticalXtype:SoilManureXSoil",
    "analyticalXtype:SoilManureXFertilizer",
    "analyticalXtype:SoilManureXManure",
    "analyticalXtype:SoilManureXPotting_Mixture",
    "family:gardening",
    "eligibility:feed",
    "eligibility:reco"
  ],
  "embedding": []
}
```

| Field | Meaning |
| --- | --- |
| `missionId` | Stable mission identity. |
| `missionName` | Mission display name. |
| `description` | Mission semantic description. |
| `tags` | Mission metadata: daypart, event, product spaces, family, and eligibility. |
| `embedding` | Mission semantic vector used by feed retrieval. |

One event is represented by one tag. For example, `event:summer` and
`event:monsoon` are separate entries in `tags`.

`eligibility:feed` admits a mission to profile-driven mission ANN retrieval.
`eligibility:reco` admits it to mapping-driven in-session ATC recommendation.
A mission can carry either or both eligibility tags.

Every feed-eligible mission has exactly one `family:<familyName>` tag. Family
is not a retrieval filter. It is the final mission-list diversity key: only one
mission from a family may occupy a feed mission slot list.

The product membership mapping for a mission will be defined with the
mission-detail endpoint, not in this section.

## 5. User category runtime profile

The record key is:

```text
userId_category
```

Example:

```text
DE2CF7945D_category
```

`userId_category` is one user-level record. It contains a profile for every
analytical category available for that user; it is not one record per category.

The record value directly contains base embeddings and matching
daypart/day-type embeddings for every category. It contains no query text and
no `queryOrder`. Array position is the fixed priority: position `0` is
strongest, position `1` is supporting, and position `2` is broader.

```json
{
  "categories": [
    {
      "analyticalVertical": "Milk",
      "base": {
        "missionEmbeddings": [[], [], []],
        "productEmbeddings": [[], [], []]
      },
      "daypartProfiles": [
        {
          "daypart": "afternoon",
          "dayType": "weekday",
          "missionEmbeddings": [[], [], []],
          "productEmbeddings": [[], [], []]
        }
      ]
    },
    {
      "analyticalVertical": "Bread",
      "base": {
        "missionEmbeddings": [[], [], []],
        "productEmbeddings": [[], [], []]
      },
      "daypartProfiles": []
    }
  ]
}
```

Runtime activation:

```text
For every category, always use its base embeddings.

For that category, use a daypart profile only when:
request.daypart == daypartProfile.daypart
AND
request.dayType == daypartProfile.dayType
```

The exact number of embeddings is limited to the populated positions. Empty
arrays are examples only; production records hold vectors of the configured
embedding dimension.

## 6. User basket runtime profile

The record key is:

```text
userId_basket
```

Example:

```text
DE2CF7945D_basket
```

This is one user-wide cross-category record. It captures what the user tends
to buy together and therefore has no analytical category at its root.

```json
{
  "base": {
    "missionEmbeddings": [[], [], []],
    "productEmbeddings": [[], [], []]
  },
  "daypartProfiles": [
    {
      "daypart": "evening",
      "dayType": "weekday",
      "missionEmbeddings": [[], [], []],
      "productEmbeddings": [[], [], []]
    }
  ]
}
```

The base embeddings are always available. A basket daypart profile is available
only when both request `daypart` and `dayType` match it. The embedding array
positions have the same fixed priority convention as the category profile.

## 7. User global runtime profile

The record key is:

```text
userId_global
```

Example:

```text
DE2CF7945D_global
```

This is one user-wide record containing overall user understanding, broader
mission/product spaces, and commercial preference metadata.

```json
{
  "brandCategory": "local",
  "brandTier": "mass_premium",
  "priceTier": "mid",
  "embedding": [],
  "base": {
    "missionEmbeddings": [[], [], []],
    "productEmbeddings": [[], [], []]
  }
}
```

| Field | Meaning |
| --- | --- |
| `brandCategory` | Overall preferred commercial brand class, for example `d2c`, `cheap`, or `local`. |
| `brandTier` | Overall preferred brand tier. |
| `priceTier` | Overall preferred price tier. |
| `embedding` | Overall user-global embedding. |
| `base` | Base mission and product embeddings. |

Global base embeddings are always available. A global profile has no
`daypartProfiles`.

## 8. Location runtime profiles

Location records are derived from collective behavior for a location. For the
current feed request, location ID is the hex ID.

```text
locationId_category
locationId_global
```

Examples:

```text
HEX_456_category
HEX_456_global
```

`locationId_category` has the same `categories[]` shape as `userId_category`:

```json
{
  "categories": [
    {
      "analyticalVertical": "Milk",
      "base": {
        "missionEmbeddings": [[], [], []],
        "productEmbeddings": [[], [], []]
      },
      "daypartProfiles": [
        {
          "daypart": "morning",
          "dayType": "weekday",
          "missionEmbeddings": [[], [], []],
          "productEmbeddings": [[], [], []]
        }
      ]
    }
  ]
}
```

`locationId_global` has the same global shape:

```json
{
  "brandCategory": "local",
  "brandTier": "value",
  "priceTier": "low",
  "embedding": [],
  "base": {
    "missionEmbeddings": [[], [], []],
    "productEmbeddings": [[], [], []]
  }
}
```

There is no location basket runtime profile at this stage.

## 9. In-session runtime box

The record key is:

```text
userId_insession
```

Example:

```text
DE2CF7945D_insession
```

In-session holds current state only. It does not store global, mission, or
product embeddings. The feed looks up activity-product catalog metadata when
it uses session candidates.

```json
{
  "timestamp": "2026-08-13T18:30:00+05:30",
  "atcProductIds": ["P90210", "P11842"],
  "activities": [
    {
      "activityType": "ppv",
      "productId": "P44501",
      "timestamp": "2026-08-13T18:27:00+05:30"
    },
    {
      "activityType": "purchase",
      "productId": "P77219",
      "timestamp": "2026-08-13T18:29:00+05:30"
    }
  ]
}
```

| Field | Meaning |
| --- | --- |
| `timestamp` | Session update time and TTL anchor. |
| `atcProductIds` | Current add-to-cart state. |
| `activities` | Current product activity and each event's time. |

## 10. Event runtime profile

Each event has one shared runtime record. The feed reads one record for every
ID in request `eventIds`.

The record key is:

```text
eventId_profile
```

Examples:

```text
monsoon_profile
match_day_profile
```

```json
{
  "eventId": "monsoon",
  "missionEmbeddings": [[], [], []],
  "productEmbeddings": [[], [], []]
}
```

| Field | Meaning |
| --- | --- |
| `eventId` | Event identity; seasons are represented as event IDs. |
| `missionEmbeddings` | Shared mission-query embeddings for this event. |
| `productEmbeddings` | Shared product-query embeddings for this event. |

Event records do not carry user identity, category profiles, daypart profiles,
or commercial preferences. Every requested event is an independent mission
candidate source and is combined through the standard importance allocation and
queue merge.

## 11. Mission retrieval for category, basket, global, location, event, and in-session

Category, basket, global, location, and event mission embeddings retrieve
candidates from the mission ANN index. In-session ATC retrieves direct mission
candidates from the product-to-mission mapping.

### 11.1 Mission query elements

For each source, activate its base `missionEmbeddings` and, when it matches the
request, its daypart-profile `missionEmbeddings`:

```text
user category: every category base embedding
             + matching category daypart embedding

user basket:   basket base embedding
             + matching basket daypart embedding

user global:   global base embedding

location category: for every request hex, every location category base embedding
                 + matching location category daypart embedding

location global:   for every request hex, location global base embedding

event:         every `eventId_profile` mission embedding for an ID in
               request.eventIds
```

Every active embedding becomes one independently executable mission query
element. The query element, not the raw profile, is the unit of retrieval,
importance, merging, and diagnostics.

```json
{
  "queryElementId": "user_category:Milk:base:mission:0",
  "source": "user_category",
  "sourceName": "Milk",
  "target": "mission",
  "embedding": [],
  "importance": 0.0,
  "filters": [
    {
      "field": "tags",
      "op": "match",
      "values": [
        "eligibility:feed",
        "daypart:all_day",
        "daypart:evening",
        "analyticalVertical:Milk"
      ]
    }
  ]
}
```

`queryElementId` is a required stable identity. It is not derived from the
embedding and must remain distinct even when two profile embeddings are equal.
It is the identity used for candidate-result maps, merging, cursors, and
diagnostics.

| Field | Meaning |
| --- | --- |
| `queryElementId` | Stable identity for one active profile embedding. |
| `source` | `user_category`, `user_basket`, `user_global`, `location_category`, `location_global`, or `event`. |
| `sourceName` | Category name for category elements, event ID for event elements, otherwise `base`. |
| `target` | `mission` for this section. |
| `embedding` | Direct mission-query embedding from the runtime profile. |
| `importance` | Final active candidate-generator importance. All active mission query-element importance sums to exactly `1.0`, calculated through Section 11.4. |
| `filters` | Food-style tag filters applied by the mission ANN executor. |

The same shape is used for every active category, basket, global, location,
and event mission embedding. Only `queryElementId`, source fields, embedding,
and event filter change. The element ID encodes whether it originated from
base or a daypart profile. Location IDs are encoded before category names, for
example `location_category:HEX_456:Milk:base:mission:0`. Event IDs use
`event:<eventId>:mission:<position>`.

### 11.2 Hard mission filters

Basket, user-global, and location-global mission query elements execute one
ANN query and apply this Food-style tag filter:

```json
[
  {
    "field": "tags",
    "op": "match",
    "values": [
      "eligibility:feed",
      "daypart:all_day",
      "daypart:<request.daypart>"
    ]
  }
]
```

Its execution semantics are the same as Food Inference:

```text
values with the same tag prefix -> OR
values with different tag prefixes -> AND
```

Therefore, an evening request means:

```text
eligibility:feed
AND
(daypart:all_day OR daypart:evening)
```

User-category and location-category mission query elements use the same base
filter and add the query element's analytical vertical:

```text
eligibility:feed
AND
(daypart:all_day OR daypart:<request.daypart>)
AND
analyticalVertical:<queryElement.sourceName>
```

For example, the `user_category:Milk:base:mission:0` element includes
`analyticalVertical:Milk`, as shown in its query-element contract above. The
same rule applies to `location_category:HEX_456:Milk:*` elements.

An event mission query element has a separate filter containing only its own
event tag. For the `monsoon_profile` record, the filter is:

```json
[
  {
    "field": "tags",
    "op": "match",
    "values": [
      "event:monsoon"
    ]
  }
]
```

This means:

```text
event:monsoon
```

The filter is applied inside the ANN query. A mission that fails feed
eligibility or daypart admission (for category, basket, global, and location
elements), category-vertical admission (for category elements), or event
admission (for an event element), is never returned as a candidate. Each query
element retains its own result list ordered by that element's ANN score.

At this stage, user-category and location-category retrieval applies only its
own `analyticalVertical` tag. Basket, global, and location-global retrieval
does not apply an analytical-vertical filter. No non-event element applies an
`analyticalXtype` or event tag; an event element applies only its own
`event:<eventId>` tag. Other scopes are not added implicitly.

### 11.3 In-session ATC mission candidates

In-session mission intent uses only the current `atcProductIds`. It does not
run mission ANN and it does not write vectors into `userId_insession`.

The mapping store exposes the reverse relation:

```text
productId -> missionIds[]
```

For every ATC product, feed reads its mapped mission IDs, retains only missions
tagged `eligibility:reco`, then unions the remaining mission IDs across the
cart. It ranks a mission by its number of distinct supporting ATC products.
This preserves more than one simultaneous cart intent instead of forcing
unrelated products into one combined embedding.

```json
{
  "source": "insession_atc",
  "missionId": "breakfast_essentials",
  "supportedByProductIds": ["P90210", "P11842", "P77110"],
  "supportCount": 3
}
```

The in-session queue is ordered by `supportCount` descending. No mapped ATC
product means no in-session mission queue. Unmapped ATC products do not use a
semantic fallback in this contract.

### 11.4 Importance allocation

Importance is a page-capacity budget, not an ANN similarity score. Every
active mission candidate source receives a budget, and all active budgets
always sum to exactly `1.0`.

```text
in-session ATC
user category
user basket
user global
location category
location global
event
--------------------
sum of active source-family importance = 1.0
```

Feed calculates a raw source-family importance only for sources with usable
candidates, then normalizes the raw values:

```text
sourceImportance(source) = rawSourceImportance(source)
                           / sum(rawSourceImportance(active sources))
```

Raw source importance is configuration-led and context-sensitive:

| Source family | Raw-importance input |
| --- | --- |
| `insession_atc` | Current-cart clarity: number of mapped ATC products and how strongly they converge on one or more missions. |
| User category and basket | User-profile depth: populated active query vectors and matching daypart coverage. |
| User global | Populated global query vectors plus its configured exploration multiplier. This share can be intentionally larger than a narrow category source because global queries include broader directions. |
| Location category and location global | Location coverage for request hexes; this share may rise when user understanding is shallow or absent. |
| Event | Presence of each requested event profile and its usable candidate queue. |

The feed owns the configurable source multipliers. No source with no usable
queue receives importance; remaining active sources are renormalized.

Each source-family budget is then split across its active profiles. These
profile allocations sum to the source-family budget. For example, a user
category budget is split over active category base/daypart profiles; a location
category budget is split over active hex/category base/daypart profiles; and
an event budget is split over active event profiles.

Finally, a profile allocation is split across its populated ordered query
vectors. Query-vector priority is strictly decreasing by array position:

```text
query[0] importance > query[1] importance > query[2] importance
sum(query importance for one profile) = profile allocation
```

The decreasing split is feed configuration and is renormalized over populated
positions. The final importance of every ANN query element is therefore:

```text
source-family allocation
× profile allocation within that source
× normalized ordered-query allocation within that profile
```

The direct `insession_atc` queue has no query-vector split: its source-family
allocation is its final queue importance. Its internal `supportCount` ranks
missions only within that queue.

### 11.5 Importance-based queue merge

The merge stage receives one ordered candidate queue per active ANN query
element, plus the optional direct in-session queue:

```text
Map<queryElementId, ordered ANN mission candidates>
plus
ordered in-session ATC mission candidates
```

It allocates mission slots from final queue importance, not by directly sorting
ANN scores from different elements against one another. Candidate ANN score
ranks missions *inside* its own ANN queue; `supportCount` ranks missions inside
the ATC queue. Importance decides how much page capacity each queue receives.

```text
sum(final importance of all active mission queues) = 1.0
```

For a request with `pageSize = N`, merge follows this sequence:

1. Normalize final active queue importance defensively to `1.0`.
2. Give each queue `floor(N × queueImportance)` initial slots.
3. Distribute unassigned slots proportionally to the remaining fractional
   quota, so final allocation stays as close as possible to importance.
4. Take candidates in each queue's own order. A selected mission is removed
   from every other queue by mission ID.
5. Read the candidate's `family:<familyName>` tag and reject it when that
   family has already occupied a final mission slot. A final mission list has
   at most one mission from each family. If a candidate is rejected for
   duplicate mission ID or duplicate family, take the next eligible candidate
   from the same queue before transferring that queue's capacity elsewhere.
6. If a queue is exhausted, return its unused capacity to remaining active
   queues. Refill using importance deficit: the queue furthest below its
   importance-proportional allocation gets the next available slot.
7. Stop when `N` missions are selected or every queue is exhausted.

This is the feed merge behavior: source importance gives each candidate source
space; queue-local rank chooses the mission inside that space; global
deduplication and the one-mission-per-family rule prevent repeated mission
themes from consuming the page. No separate final mission L2 ranking is
performed.

## 12. Product retrieval and ranking

Product candidate sources are independent queues, exactly like mission
candidate sources. This section defines the current product sources:

```text
user category       -> base + matching daypart product embeddings
user basket         -> base + matching daypart product embeddings
user global         -> base product embeddings, combined with user-global embedding
location category   -> base + matching daypart product embeddings for each request hex
location global     -> base product embeddings for each request hex
event               -> product embeddings, combined with user-global embedding
```

### 12.1 Product query elements

Every active product embedding produces one product query element. It has the
same stable identity, source, source name, direct embedding, and final
importance shape as a mission query element, but its target is `product`.

```json
{
  "queryElementId": "user_category:Milk:base:product:0",
  "source": "user_category",
  "sourceName": "Milk",
  "target": "product",
  "embedding": [],
  "importance": 0.0,
  "filters": [
    {
      "field": "analyticalVertical",
      "op": "match",
      "values": ["Milk"]
    }
  ]
}
```

Product queries have only one profile-driven hard filter: a user-category or
location-category element requires its own `analyticalVertical`. Basket,
user-global, location-global, and event product elements have no
profile-driven hard filter:

```json
{
  "filters": []
}
```

There are no product hard filters for daypart, day type, event, brand tier,
price tier, order score, or freshness score. Product serviceability for the
request hexes remains the mandatory candidate universe; it is not a
profile-driven product-query filter.

### 12.2 User-global additive product vectors

`userId_global.embedding` is the overall user embedding. Global and event
product vectors are intentionally made user-aware by adding that embedding to
the source product-query embedding before retrieval:

```text
global product element embedding
  = unitNormalize(userGlobal.embedding + global.productEmbedding)

event product element embedding
  = unitNormalize(userGlobal.embedding + event.productEmbedding)
```

Both inputs use the same embedding model and dimension. The result is unit
normalized before ANN/cosine search. This lets a broader global direction or a
shared event direction retrieve products in the context of the specific user.

Category, basket, and location product elements use their stored product-query
embeddings directly. A global or event product element is not active when its
required `userId_global.embedding` is absent; the element is skipped.

### 12.3 Product candidate ranking

Each product query element retrieves from the serviceable product universe and
orders its own result queue using semantic similarity plus configured boosts.
The boost inputs are product runtime metadata and user-global preference
metadata:

| Ranking input | Role |
| --- | --- |
| Product vector similarity | Semantic relevance inside the query element. |
| `orderScore` | Boosts products with stronger order signal. |
| `freshnessScore` | Boosts products with stronger freshness signal. |
| `brandTier` match | Boosts a product whose brand tier matches `userId_global.brandTier`. |
| `priceTier` match | Boosts a product whose price tier matches `userId_global.priceTier`. |
| `brandCategory` match | Boosts a product whose commercial brand class matches `userId_global.brandCategory`. |

These are boosts, not filters. A product outside the user's usual tier or
commercial class can still be retrieved when it is semantically appropriate.
The feed owns the calibrated boost weights and score normalization; those
weights are not profile data.

### 12.4 In-session product candidate lanes

In-session product retrieval has two independent queues. Product metadata for
all ATC, PPV, and purchase IDs is looked up from the catalog at request time.
Neither queue writes session embeddings back into `userId_insession`.

#### 12.4.1 ATC mission-expansion queue

The feed first resolves the union of missions supported by current ATC products
through the product-to-mission mapping:

```text
ATC product IDs
  -> union of mapped missions tagged eligibility:reco
  -> mission-product membership candidates
  -> serviceable products outside current ATC verticals
```

This queue recommends products belonging to the cart-supported missions, but
only from analytical verticals that are absent from the current ATC products.
It is the session cross-vertical expansion lane. ATC products and every
product in an ATC vertical are excluded from this queue.

#### 12.4.2 PPV alternative-product ANN queues

The feed takes at most the five most recent PPV products, ordered by activity
timestamp descending. For each selected PPV product, it runs one product ANN
query using that catalog product's embedding. These are separate queues; PPV
product vectors are not averaged together.

Each PPV queue boosts product alternatives with a different `brandTier` and a
different `priceTier` from the PPV product. The boosts are soft: the product
need not differ in both fields to be eligible, and same-tier products remain
available when they are semantically stronger.

```text
one of the last five PPV products
  -> its catalog embedding
  -> one serviceable-product ANN queue
  -> boost different brand-tier and price-tier alternatives
```

#### 12.4.3 Purchase deboosting

Purchase activity is a negative session signal for these two in-session lanes.
For every purchase product, feed applies configurable soft deboosts to:

1. The exact purchased `productId`.
2. All products in that purchased product's `analyticalVertical`.

The deboost applies to both the ATC mission-expansion and PPV alternative ANN
queues. It is not a hard exclusion: a product can still win when its semantic
or mission relevance is sufficiently strong. Purchase does not itself create
a product ANN queue in this contract.

### 12.5 Product importance and merge

Product queues use the same hierarchical importance model as mission queues:

```text
source-family budget
  -> active profile allocation
  -> decreasing ordered product-query allocation
  -> final product queue importance
```

All active product queue importance sums to exactly `1.0`. Source-family raw
importance is recomputed from the active product queues and then normalized;
it is not required to equal the mission source-family allocation. This allows
the feed to give global exploratory product queries more or less product-page
space independently of mission-page space.

The two in-session product lane types are independent candidate sources inside
the product importance calculation. An ATC mission-expansion queue receives
importance only when it has eligible non-ATC-vertical products. Each PPV
alternative ANN queue receives importance only when it has candidates. Their
active shares, like all other product queues, are normalized into the same
total of `1.0`.

For a product page of `N` slots, merge follows the mission merge mechanics:

1. Allocate initial queue slots from final product-queue importance.
2. Take products in each queue's boosted local rank order.
3. Deduplicate by `productId`; on rejection, advance within the same queue.
4. Return capacity from exhausted queues and refill remaining queues by
   importance deficit.
5. Stop at `N` products or when every product queue is exhausted.

### 12.6 Homepage product category and brand spacing

Category and brand diversity are enforced after product queues have been
allocated importance and before a product occupies a final homepage slot. They
are merge-time rules, never product retrieval filters.

The diversity keys are:

```text
category key = product.analyticalVertical
brand key    = product.brand
```

`brand` is the actual catalog brand, such as `Amul` or `Nandini`.
`brandCategory` remains the separate commercial class such as `d2c`, `cheap`,
or `local`; it must not be used as the brand-spacing key.

For every candidate considered by the product merge, feed applies configured
homepage limits:

```text
maxProductsPerCategory
maxProductsPerBrand
minimumCategoryGap
minimumBrandGap
```

A product is rejected when it would exceed either page-level category/brand
maximum or repeat its category/brand within the corresponding configured gap
in the final product list. When rejected, merge advances to the next candidate
from the same lane. The source's capacity transfers to another lane only after
that lane has no eligible candidate left.

Configured category and brand limits are not relaxed merely to fill the
requested product count. The product page may contain fewer than `N` products
when no eligible diverse candidate remains. This spacing applies to the
homepage product list; the product list for one mission is a separate contract.

## 13. Homepage response, product continuation, and load more

### 13.1 Homepage response

The homepage response returns the final selected missions and products from
their independent feed merges. `requestId` identifies this specific homepage
response and is the `parentRequestId` accepted by load more.

```json
{
  "requestId": "REQ_01J9M7K2",
  "missions": [
    {
      "missionId": "breakfast_essentials",
      "missionName": "Breakfast Essentials",
      "description": "Build a convenient breakfast with dairy, bread, eggs, cereals, and quick morning staples."
    }
  ],
  "products": [
    {
      "productId": "P90210",
      "productName": "Amul Taaza Toned Milk 500 ml"
    }
  ]
}
```

| Field | Meaning |
| --- | --- |
| `requestId` | Stable homepage response identity and load-more parent request ID. |
| `missions` | Final mission list after mission importance merge, deduplication, and family diversity. |
| `products` | Final homepage product list after product importance merge, ranking boosts, and category/brand spacing. |

The response does not expose candidate lanes, embeddings, ANN scores, or
importance values. Product card enrichment is performed after product selection
and does not change the selected product IDs.

Load more accepts only the homepage parent request ID:

```json
{
  "parentRequestId": "REQ_01J9M7K2",
  "pageSize": 12
}
```

`pageSize` is the requested number of products for this load-more response.
Load more does not accept user ID, hexes, daypart, day type, events, profile
data, or client-supplied session activity. Those values are inherited from the
homepage snapshot.

Load more is product continuation only. It does not return a `missions` field:

```json
{
  "parentRequestId": "REQ_01J9M7K2",
  "products": [
    {
      "productId": "P991",
      "productName": "Nandini Toned Milk 500 ml"
    }
  ]
}
```

The returned `products` are the next selected product page. Mission serving is
homepage-only and is not repeated, emptied, or represented as `missions: []`
in a load-more response.

### 13.2 Homepage Aerospike snapshot

The homepage response creates `parentRequestId` and writes one short-lived
Aerospike continuation record. Load more updates this same record after every
response, making it the continuation state for the next load-more request.

```json
{
  "parentRequestId": "REQ_01J9M7K2",
  "cacheVersion": 1,
  "snapshotTime": "2026-08-13T18:30:00+05:30",
  "requestContext": {
    "userId": "U123",
    "hexIds": ["HEX_456", "HEX_789"],
    "daypart": "evening",
    "dayType": "weekday",
    "eventIds": ["monsoon"]
  },
  "sessionBaseline": {
    "atcProductIds": ["P90210", "P11842"],
    "purchaseDeboostProductIds": [],
    "purchaseDeboostVerticals": []
  },
  "productLanes": [
    {
      "laneId": "user_category:Milk:base:product:0",
      "laneType": "ann_query_element",
      "source": "user_category",
      "baseRawImportance": 0.16,
      "rankedCandidateIds": ["P991", "P992", "P993"],
      "nextCandidateIndex": 2
    },
    {
      "laneId": "insession_ppv:P44501:product",
      "laneType": "direct_session_ann",
      "source": "insession_ppv",
      "baseRawImportance": 0.12,
      "rankedCandidateIds": ["P771", "P772"],
      "nextCandidateIndex": 0
    }
  ],
  "deliveredProductIds": ["P44501", "P77219"]
}
```

`snapshotTime` is the cutoff between already-processed session activity and
new session activity. `sessionBaseline.atcProductIds` is retained to calculate
newly added cart products. Purchase deboost product IDs and verticals are
retained so their negative session effect continues on later pages. The record
does not store the full in-session activity log.

`productLanes` contains every active homepage product QueryElement: every
category/base/daypart/global, location, event, and direct in-session product
lane. Homepage mission lanes are not cached for load more.

Each lane stores its full retrieved ranked candidate list for the cached page
window, not a flattened final ranking. `nextCandidateIndex` is advanced as the
lane contributes candidates to homepage and later load-more responses.
`baseRawImportance` is the lane's pre-normalization contribution, retained so
the feed can recompute importance when fresh session lanes appear.

The cache therefore stores the candidate list per homepage product
QueryElement/lane. It does not store every serviceable product in the catalog.

### 13.3 New in-session state after the continuation cutoff

On load more, feed captures a `continuationCutoffTime`, reads the current
in-session record, and considers only activity in this interval:

```text
new ATC product IDs = current atcProductIds - sessionBaseline.atcProductIds
new PPV activities  = PPV activities with snapshotTime < timestamp <= continuationCutoffTime
new purchases       = purchase activities with snapshotTime < timestamp <= continuationCutoffTime
```

The PPV delta is capped to its five most recent products before it creates
separate PPV ANN queues. The new ATC delta is resolved through the same
product-to-mission union used on the homepage. New purchases are added to
`purchaseDeboostProductIds` and their verticals to
`purchaseDeboostVerticals`; the full accumulated deboost set applies to the
same two in-session product lanes on every later page.

No session candidate from before `snapshotTime` is generated again. Products
delivered on the homepage or a previous load-more response remain in
`deliveredProductIds` and are never selected again.

### 13.4 Load-more merge and recache

Load more uses the same queue merge as the homepage:

1. Restore the undelivered cached product lanes.
2. Build only the new in-session product lanes from the post-snapshot delta.
3. Recompute raw source importance over restored product lanes plus new
   session product lanes, then normalize active product-queue importance to
   `1.0`.
4. Run the same quota allocation, queue-local consumption, product
   deduplication, category/brand spacing, same-lane refill, and
   importance-deficit redistribution used by the homepage.
5. Append newly delivered product IDs, append each new in-session product
   lane, and advance every consumed lane's `nextCandidateIndex`.
6. Replace `sessionBaseline.atcProductIds` with the current ATC product IDs;
   retain accumulated purchase deboost IDs and verticals; and set
   `snapshotTime` to `continuationCutoffTime`.
7. Atomically write the updated continuation record under the same
   `parentRequestId`, incrementing `cacheVersion`.

Thus load more is the same feed logic as the homepage: it reuses the cached
ranked queue tails and adjusts only for session behavior that happened after
the previous continuation cutoff. A single flat cached ranking would not be
sufficient, because it cannot give newly created in-session queues their
appropriate importance. `cacheVersion` is compared atomically during the
update; if another load-more response has already advanced the record, feed
reloads the latest continuation record and recomputes the page instead of
reusing stale lane cursors.

## 14. Products for one mission

The mission-detail endpoint uses the same product candidate sources, additive
vectors, boosts, importance allocation, queue merge, and product spacing as
the homepage. Its mandatory boundary is the requested `missionId`.

```json
{
  "userId": "U123",
  "hexIds": ["HEX_456", "HEX_789"],
  "missionId": "breakfast_essentials",
  "daypart": "evening",
  "dayType": "weekday",
  "eventIds": ["monsoon"],
  "pageSize": 12
}
```

`missionId` selects the mandatory product-membership boundary. The remaining
fields have the same meaning as the homepage request and activate the same
user, location, event, and in-session product sources.

For every product lane, eligible products are:

```text
serviceable products for request.hexIds
INTERSECT
products mapped to request.missionId
```

The mission-product mapping is the hard `missionId` filter. It is applied to
every ANN and direct-session lane before local product ranking. No product
outside the requested mission's membership is eligible, even if it scores
highly for a profile query.

### 14.1 Category lanes inside the mission boundary

The requested mission exposes its supported analytical verticals through its
`analyticalVertical:<vertical>` tags:

```text
missionVerticals = values from requested mission tags with prefix
                   analyticalVertical:
```

A user-category or location-category product lane is active only when:

```text
categoryProfile.analyticalVertical is in missionVerticals
```

When active, the category lane has both hard boundaries:

```text
product is mapped to request.missionId
AND
product.analyticalVertical = categoryProfile.analyticalVertical
```

For example, a mission tagged with `analyticalVertical:Milk` and
`analyticalVertical:Bread` may activate Milk and Bread category queries. A
Snacks category query is not created for that mission.

Basket, user-global, location-global, event, and PPV ANN product lanes do not
need a mission-vertical match. They run inside the mandatory mission-membership
boundary and can retrieve any product mapped to that mission. Their existing
profile-driven filters and boosts remain unchanged.

### 14.2 In-session and final merge

The same in-session rules apply inside the mission boundary:

- ATC mission expansion is active only when the requested `missionId` is in
  the union of `eligibility:reco` missions mapped from the current ATC
  products.
- Every PPV product may create its independent alternative-product ANN lane,
  but that lane is hard-filtered to requested-mission products.
- Purchase product and vertical deboosts apply unchanged.

All active mission-detail product lanes are normalized to total importance
`1.0`, then use the same product deduplication, category spacing, brand
spacing, same-lane refill, and importance-deficit redistribution as homepage
products. This endpoint changes eligibility, not the feed merge logic.
