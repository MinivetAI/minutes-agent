package com.minutes.explorability;

import com.minutes.explorability.ScoringModels.*;

import java.math.BigDecimal;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static com.minutes.explorability.ScoringModels.ProductScore.ScoringError.*;
import static org.junit.jupiter.api.Assertions.*;

class ConfigIntegrationTest {
    @TempDir Path temp;
    private static final String HEADER = "analytic_super_category,n,p50,p95,p99,computed_at,weight_version\n";

    private ProductInput product() {
        return new ProductInput("P1", "Grooming", "Grooming", "HairCare", "Shampoo",
                List.of(new ProductInput.Dimension("active_or_special_ingredients", List.of("onion")),
                        new ProductInput.Dimension("organic", List.of()),
                        new ProductInput.Dimension("targeted_problems", List.of("hair_fall"))));
    }

    @Test void loadsCheckedInWeightsAndComputedSupercategoryBaselines() throws Exception {
        var config = ScoringJson.readConfig(Path.of("config/dimension-weights.json"),
                Path.of("config/normalization-baselines.csv"));
        assertEquals(65, config.normalization().baselines().size());
        assertTrue(config.normalization().baselines().stream()
                .allMatch(b -> !b.analyticSuperCategory().isBlank()));
        assertTrue(config.normalization().baselines().stream().anyMatch(b -> b.p95RawScore().signum() > 0));
        var result = new ExplorabilityScorer(config).score(product());
        assertEquals(0, new BigDecimal("3").compareTo(result.rawScore()));
        assertEquals(0, new BigDecimal("0.6667").compareTo(result.exploreScore()));
        assertNull(result.error());
    }

    @Test void separatePositiveBaselineFileEnablesNormalization() throws Exception {
        Path baseline = temp.resolve("baselines.csv");
        Files.writeString(baseline, HEADER + "Grooming,100,1,4,5,2026-10-09,v1\n");
        var config = ScoringJson.readConfig(Path.of("config/dimension-weights.json"), baseline);
        var result = new ExplorabilityScorer(config).score(product());
        assertEquals(0, new BigDecimal("0.75").compareTo(result.exploreScore()));
        assertNull(result.error());
    }

    @Test void rejectsMismatchedVersionInSeparateFile() throws Exception {
        Path baseline = temp.resolve("baselines.csv");
        Files.writeString(baseline, HEADER + "Grooming,100,1,2,3,2026-10-09,another-version\n");
        assertThrows(IllegalArgumentException.class, () -> ScoringJson.readConfig(
                Path.of("config/dimension-weights.json"), baseline));
    }

    @Test void rejectsTwoBaselineSources() throws Exception {
        Path weights = temp.resolve("weights.json");
        Files.writeString(weights, """
                {"schema_version":1,"weight_version":"v1","dimensions":[],
                 "normalization":{"weight_version":"v1","baselines":[]}}
                """);
        assertThrows(IllegalArgumentException.class, () -> ScoringJson.readConfig(weights,
                Path.of("config/normalization-baselines.csv")));
    }

    @Test void scoresCannotRepresentInconsistentOrOutOfRangeStates() {
        assertThrows(IllegalArgumentException.class, () -> new ProductScore(BigDecimal.ZERO, null, null));
        assertThrows(IllegalArgumentException.class, () -> new ProductScore(BigDecimal.ONE, BigDecimal.ONE, BASELINE_CONFIG_MISSING));
        assertThrows(IllegalArgumentException.class, () -> new ProductScore(new BigDecimal("-1"), null, BASELINE_CONFIG_MISSING));
        assertThrows(IllegalArgumentException.class, () -> new ProductScore(BigDecimal.ONE, new BigDecimal("1.1"), null));
        assertThrows(IllegalArgumentException.class, () -> new MissionScore("M1", new BigDecimal("1.1")));
    }

    @Test void scoreSerializationPreservesNumericValues() throws Exception {
        var score = new ProductScore(new BigDecimal("10"), BigDecimal.ONE, null);
        assertEquals("{\"raw_score\":10,\"explore_score\":1,\"error\":null}",
                ScoringJson.writeScore(score));
    }

    @Test void rejectsNullJsonDocuments() {
        assertThrows(IllegalArgumentException.class, () -> ScoringJson.readConfig("null"));
        assertThrows(IllegalArgumentException.class, () -> ScoringJson.readProduct("null"));
        assertThrows(IllegalArgumentException.class, () -> ScoringJson.readMission("null"));
    }

    @Test void immutableScorerCanBeReusedConcurrently() throws Exception {
        var scorer = new ExplorabilityScorer(ScoringJson.readConfig(Path.of("config/dimension-weights.json"),
                Path.of("config/normalization-baselines.csv")));
        var expected = scorer.score(product());
        assertTrue(java.util.stream.IntStream.range(0, 200).parallel()
                .mapToObj(i -> scorer.score(product())).allMatch(expected::equals));
    }

    @Test void supercategoryBaselineAppliesAcrossChildTaxonomies() throws Exception {
        Path baseline = temp.resolve("baselines.csv");
        Files.writeString(baseline, HEADER + "BabyCare,1240,2.1,6.8,8.4,2026-10-09,v1\n");
        var scorer = new ExplorabilityScorer(ScoringJson.readConfig(Path.of("config/dimension-weights.json"), baseline));
        for (String category : List.of("BabyCareOthers", "BabyGear")) {
            var p = new ProductInput("P1", "BabyCare", category, "BabyGear", "FeedingBottle",
                    List.of(new ProductInput.Dimension("organic", List.of())));
            var result = scorer.score(p);
            assertEquals(0, result.rawScore().divide(new BigDecimal("6.8"), 4, java.math.RoundingMode.HALF_UP)
                    .compareTo(result.exploreScore()));
        }
    }

    @Test void categoryFieldsAreRejectedInEmbeddedBaselineConfig() {
        assertThrows(Exception.class, () -> ScoringJson.readConfig("""
                {"schema_version":1,"weight_version":"v1","dimensions":[],
                 "normalization":{"weight_version":"v1","baselines":[{
                   "analytic_super_category":"Grooming","analytic_category":"Grooming",
                   "p95_raw_score":2}]}}
                """));
    }

    @Test void rejectsDuplicateCsvScopesAndIncorrectHeaders() throws Exception {
        Path baseline = temp.resolve("invalid.csv");
        String row = "Grooming,100,1,2,3,2026-10-09,v1\n";
        Files.writeString(baseline, HEADER + row + row);
        assertThrows(IllegalArgumentException.class, () -> new ExplorabilityScorer(ScoringJson.readConfig(
                Path.of("config/dimension-weights.json"), baseline)));
        Files.writeString(baseline, "analytic_super_category,p95\nGrooming,2\n");
        assertThrows(IllegalArgumentException.class, () -> ScoringJson.readConfig(
                Path.of("config/dimension-weights.json"), baseline));
    }
}
