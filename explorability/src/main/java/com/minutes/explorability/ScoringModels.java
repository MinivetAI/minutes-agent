package com.minutes.explorability;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonValue;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import java.math.BigDecimal;
import java.util.List;

/** Immutable inputs, configs and results shared by both scoring functions. */
public final class ScoringModels {
    private ScoringModels() {}

    /** Exact parent-qualified taxonomy scope, from supercategory through vertical. */
    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record TaxonomyScope(
            String analyticSuperCategory,
            String analyticCategory,
            String analyticSubCategory,
            String analyticVertical) {

        public TaxonomyScope {
            ScoringModels.text(analyticSuperCategory, "analytic_super_category");
            if (analyticCategory != null) ScoringModels.text(analyticCategory, "analytic_category");
            if (analyticSubCategory != null) ScoringModels.text(analyticSubCategory, "analytic_sub_category");
            if (analyticVertical != null) ScoringModels.text(analyticVertical, "analytic_vertical");
            if ((analyticCategory == null && (analyticSubCategory != null || analyticVertical != null))
                    || (analyticSubCategory == null && analyticVertical != null)) {
                throw new IllegalArgumentException("Scopes must include all parent taxonomy fields");
            }
        }

        public int depth() {
            return analyticVertical != null ? 4 : analyticSubCategory != null ? 3
                    : analyticCategory != null ? 2 : 1;
        }
    }

    /** Immutable weights and optional p99 baselines from the same weight version. */
    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record ScoringConfig(
            int schemaVersion,
            String weightVersion,
            List<DimensionWeight> dimensions,
            Normalization normalization) {

        public ScoringConfig {
            if (schemaVersion != 1) throw new IllegalArgumentException("Unsupported schema_version");
            ScoringModels.text(weightVersion, "weight_version");
            dimensions = ScoringModels.list(dimensions, "dimensions");
            if (normalization != null && !weightVersion.equals(normalization.weightVersion())) {
                throw new IllegalArgumentException("Normalization baselines must use the same weight_version");
            }
        }

        @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
        public record DimensionWeight(String dimensionId, BigDecimal defaultWeight, List<WeightOverride> overrides) {
            public DimensionWeight {
                ScoringModels.text(dimensionId, "dimension_id");
                ScoringModels.weight(defaultWeight, "default_weight");
                overrides = overrides == null ? List.of() : ScoringModels.list(overrides, "overrides");
            }
        }

        public record WeightOverride(TaxonomyScope scope, BigDecimal weight) {
            public WeightOverride {
                if (scope == null) throw new IllegalArgumentException("Override scope is required");
                ScoringModels.weight(weight, "override weight");
            }
        }

        @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
        public record Normalization(String weightVersion, List<Baseline> baselines) {
            public Normalization {
                ScoringModels.text(weightVersion, "normalization.weight_version");
                baselines = ScoringModels.list(baselines, "normalization.baselines");
            }
        }

        @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
        public record Baseline(String analyticSuperCategory, BigDecimal p99RawScore) {
            public Baseline {
                ScoringModels.text(analyticSuperCategory, "baseline analytic_super_category");
                if (p99RawScore == null || p99RawScore.signum() < 0) {
                    throw new IllegalArgumentException("p99_raw_score must be non-negative");
                }
            }
        }
    }

    /** Only positively qualified dimensions belong in this input. Values do not affect weights. */
    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record ProductInput(
            @JsonProperty("productId") String productId,
            String analyticSuperCategory,
            String analyticCategory,
            String analyticSubCategory,
            String analyticVertical,
            List<Dimension> dimensions) {

        public ProductInput {
            ScoringModels.text(productId, "productId");
            ScoringModels.text(analyticSuperCategory, "analytic_super_category");
            ScoringModels.text(analyticCategory, "analytic_category");
            ScoringModels.text(analyticSubCategory, "analytic_sub_category");
            ScoringModels.text(analyticVertical, "analytic_vertical");
            dimensions = ScoringModels.list(dimensions, "dimensions");
        }

        @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
        public record Dimension(String dimensionId, List<String> values) {
            public Dimension {
                ScoringModels.text(dimensionId, "dimension_id");
                values = values == null ? List.of() : ScoringModels.list(values, "values");
                values.forEach(value -> ScoringModels.text(value, "dimension value"));
            }
        }
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    @JsonInclude(JsonInclude.Include.ALWAYS)
    public record ProductScore(BigDecimal rawScore, BigDecimal exploreScore, ScoringError error) {
        public ProductScore {
            if (rawScore == null || rawScore.signum() < 0) {
                throw new IllegalArgumentException("A non-negative raw_score is required");
            }
            if (error == null) {
                ScoringModels.score(exploreScore, "explore_score");
            } else if (exploreScore != null) {
                throw new IllegalArgumentException("baseline_config_missing requires explore_score to be null");
            }
        }

        public enum ScoringError {
            BASELINE_CONFIG_MISSING("baseline_config_missing");

            private final String value;
            ScoringError(String value) { this.value = value; }
            @JsonValue public String value() { return value; }
        }
    }

    /** One normalized score per product in this mission. Raw or missing scores are not valid inputs. */
    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record MissionInput(
            @JsonProperty("missionId") String missionId,
            List<BigDecimal> productExploreScores) {
        public MissionInput {
            ScoringModels.text(missionId, "missionId");
            productExploreScores = ScoringModels.list(productExploreScores, "product_explore_scores");
            if (productExploreScores.isEmpty()) {
                throw new IllegalArgumentException("A mission requires at least one normalized product score");
            }
            productExploreScores.forEach(score -> ScoringModels.score(score, "product_explore_scores entry"));
        }
    }

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record MissionScore(@JsonProperty("missionId") String missionId, BigDecimal exploreScore) {
        public MissionScore {
            ScoringModels.text(missionId, "missionId");
            ScoringModels.score(exploreScore, "explore_score");
        }
    }

    private static String text(String value, String name) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(name + " must be non-blank");
        }
        return value;
    }

    private static <T> List<T> list(List<T> values, String name) {
        if (values == null || values.stream().anyMatch(v -> v == null)) {
            throw new IllegalArgumentException(name + " must be a list without null entries");
        }
        return List.copyOf(values);
    }

    private static BigDecimal weight(BigDecimal value, String name) {
        if (value == null || value.signum() < 0 || value.compareTo(BigDecimal.ONE) > 0) {
            throw new IllegalArgumentException(name + " must be in [0,1]");
        }
        return value;
    }

    private static BigDecimal score(BigDecimal value, String name) {
        if (value == null || value.signum() < 0 || value.compareTo(BigDecimal.ONE) > 0) {
            throw new IllegalArgumentException(name + " must be a normalized score in [0,1]");
        }
        return value;
    }
}
