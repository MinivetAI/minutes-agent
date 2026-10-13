package com.minutes.explorability;

import com.minutes.explorability.ScoringModels.*;

import java.math.BigDecimal;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.junit.jupiter.api.Test;
import com.minutes.explorability.ScoringModels.ProductInput.Dimension;
import com.minutes.explorability.ScoringModels.ScoringConfig.*;
import static com.minutes.explorability.ScoringModels.ProductScore.ScoringError.*;
import static org.junit.jupiter.api.Assertions.*;

class ProductScorerTest {
    private static BigDecimal decimal(String value) { return new BigDecimal(value); }
    private static TaxonomyScope scope(int depth) {
        return new TaxonomyScope("Grooming", depth >= 2 ? "Grooming" : null,
                depth >= 3 ? "HairCare" : null, depth >= 4 ? "Shampoo" : null);
    }
    private static DimensionWeight dimension(String id, String weight, WeightOverride... overrides) {
        return new DimensionWeight(id, decimal(weight), List.of(overrides));
    }
    private static Dimension qualified(String id, String... values) {
        return new Dimension(id, List.of(values));
    }
    private static ProductInput product(Dimension... dimensions) {
        return new ProductInput("P1", "Grooming", "Grooming", "HairCare", "Shampoo", List.of(dimensions));
    }
    private static ScoringConfig config(List<DimensionWeight> dimensions, Baseline... baselines) {
        return new ScoringConfig(1, "v1", dimensions,
                baselines.length == 0 ? null : new Normalization("v1", List.of(baselines)));
    }
    private static ProductScore score(ProductInput product, ScoringConfig config) {
        return new ExplorabilityScorer(config).score(product);
    }
    private static void assertDecimal(String expected, BigDecimal actual) {
        assertNotNull(actual);
        assertEquals(0, decimal(expected).compareTo(actual));
    }

    @Test void checkedInConfigScoresProductWithoutBaseline() throws Exception {
        var scorer = new ExplorabilityScorer(ScoringJson.readConfig(Path.of("config/dimension-weights.json")));
        var result = scorer.score(product(qualified("premium_brand"), qualified("premium_sku"),
                qualified("organic"), qualified("brand_tier", "premium_branded"),
                qualified("sku_tier", "premium_branded")));
        assertDecimal("3", result.rawScore());
        assertNull(result.exploreScore());
        assertEquals(BASELINE_CONFIG_MISSING, result.error());
    }

    @Test void returnsRawWithoutClampingWhenBaselineIsMissing() {
        var c = config(List.of(dimension("a", "0.25"), dimension("b", "0.5"), dimension("c", "1")));
        var result = score(product(qualified("a"), qualified("b"), qualified("c")), c);
        assertDecimal("1.75", result.rawScore());
        assertNull(result.exploreScore());
    }

    @Test void appliesEachScopeAndIgnoresOverrideArrayOrder() {
        var overrides = List.of(new WeightOverride(scope(1), decimal("0.25")),
                new WeightOverride(scope(2), decimal("0.5")),
                new WeightOverride(scope(3), decimal("1")),
                new WeightOverride(scope(4), decimal("0.25")));
        for (int depth = 0; depth <= 4; depth++) {
            var p = new ProductInput("P1", depth >= 1 ? "Grooming" : "Unknown",
                    depth >= 2 ? "Grooming" : "Unknown", depth >= 3 ? "HairCare" : "Unknown",
                    depth >= 4 ? "Shampoo" : "Unknown", List.of(qualified("a")));
            var reversed = new ArrayList<>(overrides);
            Collections.reverse(reversed);
            var scorer = new ExplorabilityScorer(config(List.of(new DimensionWeight("a", decimal("0"), reversed))));
            assertDecimal(new String[]{"0", "0.25", "0.5", "1", "0.25"}[depth], scorer.score(p).rawScore());
        }
    }

    @Test void explicitZeroOverridesParentWithoutZeroingOtherDimensions() {
        var c = config(List.of(dimension("a", "0.5", new WeightOverride(scope(4), BigDecimal.ZERO)),
                dimension("b", "0.25")));
        assertDecimal("0.25", score(product(qualified("a"), qualified("b")), c).rawScore());
    }

    @Test void duplicateAndMultivaluedDimensionsContributeOnce() {
        var c = config(List.of(dimension("a", "0.5")));
        assertDecimal("0.5", score(product(qualified("a", "x", "y"),
                qualified("a", "z")), c).rawScore());
    }

    @Test void valuesDoNotChangeWeights() {
        var c = config(List.of(dimension("a", "0.5")));
        assertEquals(score(product(qualified("a", "onion")), c),
                score(product(qualified("a", "unknown_value")), c));
    }

    @Test void unknownDimensionsAndOldAliasesContributeZero() {
        var c = config(List.of(dimension("organic", "1")));
        assertDecimal("1", score(product(qualified("organic"),
                qualified("organic"), qualified("unknown")), c).rawScore());
    }

    @Test void scopeRequiresExactParentPath() {
        var c = config(List.of(dimension("a", "0.5", new WeightOverride(scope(4), decimal("1")))));
        var p = new ProductInput("P1", "DifferentSupercategory", "Grooming", "HairCare", "Shampoo", List.of(qualified("a")));
        assertDecimal("0.5", score(p, c).rawScore());
    }

    @Test void usesExactSupercategoryBaseline() {
        var c = config(List.of(dimension("a", "0.5")), new Baseline("Grooming", decimal("1")));
        var result = score(product(qualified("a")), c);
        assertDecimal("0.5", result.exploreScore());
        assertNull(result.error());
    }

    @Test void zeroSupercategoryBaselineMeansMissingNormalization() {
        var c = config(List.of(dimension("a", "0.5")), new Baseline("Grooming", BigDecimal.ZERO));
        var result = score(product(qualified("a")), c);
        assertNull(result.exploreScore());
        assertEquals(BASELINE_CONFIG_MISSING, result.error());
    }

    @Test void baselineFromDifferentParentCannotNormalizeProduct() {
        var c = config(List.of(dimension("a", "0.5")),
                new Baseline("Other", decimal("1")));
        assertNull(score(product(qualified("a")), c).exploreScore());
    }

    @Test void emptyProductDimensionsReturnZeroRawAndOnlyNormalizeWhenBaselineExists() {
        assertNull(score(product(), config(List.of())).exploreScore());
        assertDecimal("0", score(product(),
                config(List.of(), new Baseline("Grooming", decimal("1")))).exploreScore());
    }

    @Test void normalizedScoresStayInRangeIncludingAtAndAboveP95() {
        for (int weight = 0; weight <= 100; weight++) {
            for (String baseline : List.of("0.01", "0.5", "1", "3")) {
                var c = config(List.of(new DimensionWeight("a", BigDecimal.valueOf(weight, 2), List.of())),
                        new Baseline("Grooming", decimal(baseline)));
                var result = score(product(qualified("a")), c);
                assertTrue(result.exploreScore().signum() >= 0);
                assertTrue(result.exploreScore().compareTo(BigDecimal.ONE) <= 0);
                if (result.rawScore().compareTo(decimal(baseline)) >= 0) assertDecimal("1", result.exploreScore());
            }
        }
    }

    @Test void fractionalRatiosAreDeterministic() {
        var scorer = new ExplorabilityScorer(config(List.of(dimension("a", "1")), new Baseline("Grooming", decimal("3"))));
        var result = scorer.score(product(qualified("a")));
        assertDecimal("0.3333", result.exploreScore());
        assertEquals(result, scorer.score(product(qualified("a"))));
    }

    @Test void rejectsInvalidWeightsScopesVersionsAndBaselines() {
        for (String invalid : List.of("-0.01", "1.01")) {
            assertThrows(IllegalArgumentException.class, () -> dimension("a", invalid));
            assertThrows(IllegalArgumentException.class, () -> new WeightOverride(scope(1), decimal(invalid)));
        }
        assertThrows(IllegalArgumentException.class, () -> new TaxonomyScope("Grooming", null, "HairCare", null));
        assertThrows(IllegalArgumentException.class, () -> new Baseline(" ", decimal("1")));
        assertThrows(IllegalArgumentException.class, () -> new Baseline("Grooming", decimal("-1")));
        assertThrows(IllegalArgumentException.class, () -> new ScoringConfig(1, "v1", List.of(),
                new Normalization("v2", List.of())));
    }

    @Test void rejectsDuplicateDimensionsScopesAndBaselines() {
        assertThrows(IllegalArgumentException.class, () -> new ExplorabilityScorer(
                config(List.of(dimension("a", "0.5"), dimension("a", "1")))));
        var duplicateScopes = dimension("a", "0.5", new WeightOverride(scope(1), decimal("0.25")),
                new WeightOverride(scope(1), decimal("1")));
        assertThrows(IllegalArgumentException.class, () -> new ExplorabilityScorer(config(List.of(duplicateScopes))));
        assertThrows(IllegalArgumentException.class, () -> new ExplorabilityScorer(config(List.of(),
                new Baseline("Grooming", decimal("1")), new Baseline("Grooming", decimal("2")))));
    }

    @Test void productAndConfigListsCannotMutateAfterConstruction() {
        var entries = new ArrayList<>(List.of(qualified("a")));
        var p = new ProductInput("P1", "Grooming", "Grooming", "HairCare", "Shampoo", entries);
        entries.clear();
        var weights = new ArrayList<>(List.of(dimension("a", "0.5")));
        var c = config(weights); weights.clear();
        assertDecimal("0.5", score(p, c).rawScore());
        assertThrows(UnsupportedOperationException.class, () -> p.dimensions().clear());
    }

    @Test void parsesProductContractAndSerializesExplicitMissingBaselineNull() throws Exception {
        var p = ScoringJson.readProduct("""
                {"productId":"P1","analytic_super_category":"Grooming","analytic_category":"Grooming",
                 "analytic_sub_category":"HairCare","analytic_vertical":"Shampoo",
                 "dimensions":[{"dimension_id":"a","values":["onion"]},{"dimension_id":"b"}]}
                """);
        var c = config(List.of(dimension("a", "0.25"), dimension("b", "0.5")));
        assertEquals("{\"raw_score\":0.75,\"explore_score\":null,\"error\":\"baseline_config_missing\"}",
                ScoringJson.writeScore(score(p, c)));
    }

    @Test void parsesOptionalBaselineConfigAndSerializesNormalizedScore() throws Exception {
        var c = ScoringJson.readConfig("""
                {"schema_version":1,"weight_version":"v1","dimensions":[{"dimension_id":"a","default_weight":0.5}],
                 "normalization":{"weight_version":"v1","baselines":[{
                   "analytic_super_category":"Grooming","p95_raw_score":2}]}}
                """);
        assertEquals("{\"raw_score\":0.5,\"explore_score\":0.25,\"error\":null}",
                ScoringJson.writeScore(score(product(qualified("a")), c)));
    }

    @Test void rejectsObsoleteValueOverridesMissingWeightsAndMalformedJson() {
        assertThrows(Exception.class, () -> ScoringJson.readConfig("""
                {"schema_version":1,"weight_version":"v1","dimensions":[{
                 "dimension_id":"a","default_weight":0.5,"value_weights":{"onion":0.6}}]}
                """));
        assertThrows(Exception.class, () -> ScoringJson.readConfig("""
                {"schema_version":1,"weight_version":"v1","dimensions":[{"dimension_id":"a"}]}
                """));
        assertThrows(IllegalArgumentException.class, () -> product(new Dimension(" ", List.of())));
    }
}
