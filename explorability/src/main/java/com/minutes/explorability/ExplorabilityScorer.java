package com.minutes.explorability;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import com.minutes.explorability.ScoringModels.*;
import com.minutes.explorability.ScoringModels.ScoringConfig.WeightOverride;
import static com.minutes.explorability.ScoringModels.ProductScore.ScoringError.*;

/** Product and mission scoring. Compile product config once; reuse safely across threads. */
public final class ExplorabilityScorer {
    private static final int SCORE_DECIMAL_PLACES = 4;
    private record DimensionRule(BigDecimal defaultWeight, List<WeightOverride> overrides) {}

    private final Map<String, DimensionRule> dimensionRules;
    private final Map<String, BigDecimal> p99BySupercategory;

    public ExplorabilityScorer(ScoringConfig config) {
        Objects.requireNonNull(config, "config");
        Map<String, DimensionRule> dimensionIndex = new HashMap<>();
        for (var dimension : config.dimensions()) {
            var overrideScopes = new HashSet<TaxonomyScope>();
            for (var override : dimension.overrides()) {
                if (!overrideScopes.add(override.scope())) {
                    throw new IllegalArgumentException("Duplicate override scope for " + dimension.dimensionId());
                }
            }
            var overrides = dimension.overrides().stream()
                    .sorted(Comparator.comparingInt((WeightOverride override) -> override.scope().depth()).reversed())
                    .toList();
            var rule = new DimensionRule(dimension.defaultWeight(), overrides);
            if (dimensionIndex.putIfAbsent(dimension.dimensionId(), rule) != null) {
                throw new IllegalArgumentException("Duplicate dimension_id: " + dimension.dimensionId());
            }
        }
        dimensionRules = Map.copyOf(dimensionIndex);

        Map<String, BigDecimal> baselineIndex = new HashMap<>();
        if (config.normalization() != null) {
            for (var baseline : config.normalization().baselines()) {
                if (baselineIndex.putIfAbsent(baseline.analyticSuperCategory(), baseline.p99RawScore()) != null) {
                    throw new IllegalArgumentException("Duplicate normalization baseline supercategory");
                }
            }
        }
        p99BySupercategory = Map.copyOf(baselineIndex);
    }

    public ProductScore score(ProductInput product) {
        Objects.requireNonNull(product, "product");
        BigDecimal rawScore = calculateRawScore(product);
        BigDecimal baseline = findPositiveSupercategoryBaseline(product);

        if (baseline == null) {
            return new ProductScore(rawScore, null, BASELINE_CONFIG_MISSING);
        }

        return new ProductScore(rawScore, normalize(rawScore, baseline), null);
    }

    private BigDecimal calculateRawScore(ProductInput product) {
        BigDecimal rawScore = BigDecimal.ZERO;
        var scoredDimensionIds = new HashSet<String>();
        for (var qualified : product.dimensions()) {
            String dimensionId = qualified.dimensionId();
            // Multiple qualifications or values still contribute only one dimension weight.
            if (scoredDimensionIds.add(dimensionId)) {
                rawScore = rawScore.add(resolveWeight(dimensionId, product));
            }
        }
        return rawScore.stripTrailingZeros();
    }

    private BigDecimal resolveWeight(String dimensionId, ProductInput product) {
        DimensionRule rule = dimensionRules.get(dimensionId);
        if (rule == null) {
            return BigDecimal.ZERO;
        }

        // Overrides are ordered vertical -> subcategory -> category -> supercategory.
        for (var override : rule.overrides()) {
            if (matches(override.scope(), product)) {
                return override.weight();
            }
        }
        return rule.defaultWeight();
    }

    private static boolean matches(TaxonomyScope scope, ProductInput product) {
        return scope.analyticSuperCategory().equals(product.analyticSuperCategory())
                && (scope.analyticCategory() == null
                    || scope.analyticCategory().equals(product.analyticCategory()))
                && (scope.analyticSubCategory() == null
                    || scope.analyticSubCategory().equals(product.analyticSubCategory()))
                && (scope.analyticVertical() == null
                    || scope.analyticVertical().equals(product.analyticVertical()));
    }

    private BigDecimal findPositiveSupercategoryBaseline(ProductInput product) {
        BigDecimal baseline = p99BySupercategory.get(product.analyticSuperCategory());
        return isPositive(baseline) ? baseline : null;
    }

    private static boolean isPositive(BigDecimal value) {
        return value != null && value.signum() > 0;
    }

    private static BigDecimal normalize(BigDecimal rawScore, BigDecimal baseline) {
        if (rawScore.compareTo(baseline) >= 0) {
            return BigDecimal.ONE;
        }
        return rawScore.divide(baseline, SCORE_DECIMAL_PLACES, RoundingMode.HALF_UP)
                .stripTrailingZeros();
    }

    /** Average the 50 highest normalized product scores, or all scores when fewer than 50 exist. */
    public static MissionScore scoreMission(MissionInput mission) {
        Objects.requireNonNull(mission, "mission");
        List<BigDecimal> topScores = mission.productExploreScores().stream()
                .sorted(Comparator.reverseOrder())
                .limit(50)
                .toList();
        BigDecimal total = topScores.stream().reduce(BigDecimal.ZERO, BigDecimal::add);
        BigDecimal average = total.divide(BigDecimal.valueOf(topScores.size()),
                        SCORE_DECIMAL_PLACES, RoundingMode.HALF_UP)
                .stripTrailingZeros();
        return new MissionScore(mission.missionId(), average);
    }

    /** Calculate requested raw-score percentiles. The caller groups products by taxonomy scope. */
    public static Map<Integer, BigDecimal> calculateBaselines(
            Map<String, BigDecimal> productRawScores, int... percentiles) {
        Objects.requireNonNull(productRawScores, "productRawScores");
        if (productRawScores.isEmpty()) {
            throw new IllegalArgumentException("At least one product raw score is required");
        }
        if (productRawScores.values().stream().anyMatch(score -> score == null || score.signum() < 0)) {
            throw new IllegalArgumentException("Product raw scores must be non-negative");
        }
        List<BigDecimal> sortedScores = productRawScores.values().stream().sorted().toList();

        Map<Integer, BigDecimal> baselines = new LinkedHashMap<>();
        for (int percentile : percentiles) {
            if (percentile < 0 || percentile > 100) {
                throw new IllegalArgumentException("Percentiles must be between 0 and 100");
            }
            baselines.put(percentile, interpolatedPercentile(sortedScores, percentile).stripTrailingZeros());
        }
        return Map.copyOf(baselines);
    }

    // Linear interpolation: index = (n - 1) * q, including zero scores and singleton missions.
    private static BigDecimal interpolatedPercentile(List<BigDecimal> sortedScores, int percentile) {
        BigDecimal index = BigDecimal.valueOf(sortedScores.size() - 1)
                .multiply(BigDecimal.valueOf(percentile, 2));
        int lowerIndex = index.intValue();
        int upperIndex = Math.min(lowerIndex + 1, sortedScores.size() - 1);
        BigDecimal fraction = index.subtract(BigDecimal.valueOf(lowerIndex));
        BigDecimal lowerScore = sortedScores.get(lowerIndex);
        BigDecimal upperScore = sortedScores.get(upperIndex);
        return lowerScore.add(upperScore.subtract(lowerScore).multiply(fraction));
    }
}
