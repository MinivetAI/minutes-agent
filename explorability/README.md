# Explorability scoring

Standalone Java 17+ library in `com.minutes.explorability`. It is independent of
Minutes Agent. No server or container is required to call these functions.

The implementation has three files: `ExplorabilityScorer` (both calculations),
`ScoringModels` (typed inputs/configs/results), and `ScoringJson` (JSON/CSV loading).
For direct Java inputs, import records from `ScoringModels`.

## Build

Run from this folder:

```bash
mvn test
mvn package
```

The library is `target/explorability-scoring-0.1.0.jar`. To integrate through Maven,
publish it to your application's artifact repository, or run `mvn install` locally
and add dependency `com.minutes:explorability-scoring:0.1.0`. Maven supplies Jackson and Commons CSV
transitively; the JAR alone does not bundle dependencies.

## Configs

| File in `config/` | Purpose |
| --- | --- |
| `dimension-weights.json` | Defaults and scope-only overrides using zero, low, medium, and high importance. |
| `normalization-baselines.csv` | Baseline statistics for 65 supercategories; 59 were calculated from the 14,000-product enrichment dataset. |

Weights and every baseline row must have the same `weight_version`. Populate statistics
after all products are scored offline. Do not add category, subcategory, or vertical baselines. Sample-size
eligibility is decided offline. Recalculate affected baselines when changing weights.

The CSV columns are:

```csv
analytic_super_category,n,p50,p95,p99,computed_at,weight_version
BabyCare,1240,2.1,6.8,8.4,2026-10-09,v1
Grooming,890,2.4,7.1,9.0,2026-10-09,v1
```

These two rows illustrate the format; they are not computed baselines. Only supercategory
baselines are used. `n` is the product count;
`p50`, `p95`, and `p99` are percentiles of raw scores. Product scoring reads the supercategory,
`p95`, and `weight_version`; the remaining columns are offline metadata. Uncomputed rows
use `n=0`, zero percentiles, and a blank `computed_at`. Six supercategories absent from the
14,000-product dataset remain placeholders. A calculated P95 can also be zero when a
supercategory has no positively weighted qualifications; zero cannot be used as a divisor.

The initial config groups dimension importance into four starting weights:

| Importance | Weight | Meaning |
| --- | ---: | --- |
| Zero | 0 | Useful for matching or filtering but does not add explorability. |
| Low | 0.25 | Adds a minor reason to explore the product. |
| Medium | 0.5 | Adds a meaningful reason to explore the product. |
| High | 1 | Strongly differentiates the product and drives exploration. |

These four values keep the first config easy to review. The scorer accepts any default
or override weight from 0 through 1, so the weights can be tuned later without a code change.
Dimension IDs use the `json_tag` values from the Minutes field-name mapping. The checked-in
config has a zero default and explicit supercategory overrides for every dimension present
in that supercategory's dimension cut. The upstream service converts `brand_tier` and
`sku_tier` into the boolean dimensions `premium_brand` and `premium_sku` before scoring.
Only true boolean qualifications should be included in product input. `allergens` remains
zero because listing an allergen does not itself add explorability.

## Product input

```json
{
  "productId": "EXAMPLE_SHAMPOO",
  "analytic_super_category": "Grooming",
  "analytic_category": "Grooming",
  "analytic_sub_category": "HairCare",
  "analytic_vertical": "Shampoo",
  "dimensions": [
    { "dimension_id": "active_or_special_ingredients", "values": ["onion"] },
    { "dimension_id": "organic" },
    { "dimension_id": "targeted_problems", "values": ["hair_fall"] }
  ]
}
```

Product ID and all taxonomy fields are required and non-blank. Include only positively
qualified dimensions; omit false boolean qualifications. An empty dimension list is valid.
Use canonical `json_tag` names directly: `organic`, `active_or_special_ingredients`, etc.

Each dimension contributes once, regardless of duplicate entries or number of values.
Values do not change weights. Check overrides in order:
`vertical -> subcategory -> category -> supercategory`, then use the default weight.
Scopes must include their parent fields. Match names exactly. Unknown dimensions score
zero; unmatched scopes inherit broader weights or defaults. Explicit zero is an override.

Look up the product's exact supercategory baseline. If it is missing or zero, return
`error: "baseline_config_missing"` with the raw score and a null explore score. Normalize with `min(1, raw_score / p95_raw_score)`.

With the checked-in Grooming P95 baseline of 4.5, the example returns:

```json
{
  "raw_score": 3,
  "explore_score": 0.6667,
  "error": null
}
```

Raw scores can exceed 1. Normalized scores are always in [0,1]; no random fallback is used.

## Baseline calculation

Group products by supercategory in the calling application, then pass that group's product
IDs and raw scores to the percentile function. Do not pass normalized
explore scores, because the p95 raw-score baseline is the denominator used to create them.

```java
var rawScores = Map.of(
    "P1", new BigDecimal("0.8"),
    "P2", new BigDecimal("1.4"),
    "P3", new BigDecimal("2.1"));
var percentiles = ExplorabilityScorer.calculateBaselines(rawScores, 50, 95, 99);
```

The result maps each requested percentile to its interpolated raw score. Use
`rawScores.size()` for `n`; the caller supplies the supercategory, computation date,
and weight version when writing the baseline CSV.

## Mission input

```json
{
  "missionId": "EXAMPLE_MISSION",
  "product_explore_scores": [0, 0.2, 0.4, 0.6, 1]
}
```

Supply one **normalized** explore score per product, including valid zeros. The list must
be non-empty and every score must be in [0,1]. Null/missing scores or out-of-range scores
are rejected. Do not substitute raw product scores or silently omit unnormalized products.
A raw score below 1 cannot be distinguished from a normalized score by its number alone;
the caller must use product results whose `error` is null and `explore_score` is present.

Pass `95` or `99` directly to the mission function. Compute that percentile using
linear interpolation at index `(n - 1) * q`,
then cap each product score at it and average **all** scores. With p95, the example cap
is 0.92 and the output is `{"missionId":"EXAMPLE_MISSION","explore_score":0.424}`.
A single-product mission retains its score. An all-zero mission returns zero.
Ratios and averages are rounded to at most 4 decimal places.

## Java integration

```java
import com.minutes.explorability.ExplorabilityScorer;
import com.minutes.explorability.ScoringJson;
import java.nio.file.Path;

var config = ScoringJson.readConfig(
    Path.of("config/dimension-weights.json"),
    Path.of("config/normalization-baselines.csv"));
var scorer = new ExplorabilityScorer(config); // Create once per config; safe to reuse across threads.
var productResult = scorer.score(ScoringJson.readProduct(productJson));
var productOutputJson = ScoringJson.writeScore(productResult);

var missionResult = ExplorabilityScorer.scoreMission(ScoringJson.readMission(missionJson), 95);
var missionOutputJson = ScoringJson.writeScore(missionResult);
```

Loading only the weight file is supported and returns raw-only scores. Embedded baselines are
supported, but cannot be combined with a separate baseline file.

Invalid inputs/configs raise exceptions. Unknown JSON fields, value overrides, duplicate
config scopes/dimensions, malformed scopes, negative baselines,
and mismatched versions are rejected. Config and product inputs are immutable.
