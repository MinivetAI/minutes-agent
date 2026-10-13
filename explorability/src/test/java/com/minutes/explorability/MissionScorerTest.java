package com.minutes.explorability;

import com.minutes.explorability.ScoringModels.*;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class MissionScorerTest {
    private static MissionInput mission(String... scores) {
        return new MissionInput("M1", Arrays.stream(scores).map(BigDecimal::new).toList());
    }
    private static void assertScore(String expected, MissionScore score) {
        assertEquals("M1", score.missionId());
        assertEquals(0, new BigDecimal(expected).compareTo(score.exploreScore()));
    }

    @Test void p95CapsBeforeAveragingAllProducts() {
        // P95 = 0.92; mean(0, 0.2, 0.4, 0.6, 0.92) = 0.424.
        assertScore("0.424", ExplorabilityScorer.scoreMission(mission("0", "0.2", "0.4", "0.6", "1"), 95));
    }

    @Test void p99UsesItsOwnCapAndStillAveragesEveryProduct() {
        // P99 = 0.984; capped mean = 0.4368.
        assertScore("0.4368", ExplorabilityScorer.scoreMission(mission("0", "0.2", "0.4", "0.6", "1"), 99));
    }

    @Test void interpolatesEvenForTwoProducts() {
        assertScore("0.475", ExplorabilityScorer.scoreMission(mission("0", "1"), 95));
        assertScore("0.495", ExplorabilityScorer.scoreMission(mission("0", "1"), 99));
    }

    @Test void singleProductKeepsItsScore() {
        assertScore("0.37", ExplorabilityScorer.scoreMission(mission("0.37"), 95));
        assertScore("0.37", ExplorabilityScorer.scoreMission(mission("0.37"), 99));
    }

    @Test void zeroAndIdenticalScoreMissionsAreHandledWithoutDivisionByZero() {
        assertScore("0", ExplorabilityScorer.scoreMission(mission("0", "0", "0"), 95));
        assertScore("1", ExplorabilityScorer.scoreMission(mission("1", "1"), 99));
        assertScore("0.4", ExplorabilityScorer.scoreMission(mission("0.4", "0.4", "0.4"), 95));
    }

    @Test void zerosStayInPopulationAndAnOutlierDoesNotBecomeTheMissionScore() {
        assertScore("0.055", ExplorabilityScorer.scoreMission(
                mission("0", "0", "0", "0", "0", "0", "0", "0", "0", "1"), 95));
    }

    @Test void scoreOrderDoesNotChangeResultOrMutateCallerList() {
        var values = new ArrayList<>(mission("0.2", "0", "0.4", "1", "0.6").productExploreScores());
        var input = new MissionInput("M1", values);
        var before = List.copyOf(values);
        var result = ExplorabilityScorer.scoreMission(input, 95);
        assertEquals(before, values);
        Collections.reverse(values);
        assertEquals(result, ExplorabilityScorer.scoreMission(new MissionInput("M1", values), 95));
        values.clear();
        assertEquals(result, ExplorabilityScorer.scoreMission(input, 95));
    }

    @Test void meanRemainsInRangeAndBetweenPopulationMinimumAndOrdinaryMean() {
        for (int i = 0; i <= 100; i++) {
            var p = new MissionInput("M1", List.of(BigDecimal.ZERO, BigDecimal.valueOf(i, 2), BigDecimal.ONE));
            for (int percentile : List.of(95, 99)) {
                BigDecimal result = ExplorabilityScorer.scoreMission(p, percentile).exploreScore();
                assertTrue(result.signum() >= 0 && result.compareTo(BigDecimal.ONE) <= 0);
                assertTrue(result.multiply(BigDecimal.valueOf(3))
                        .compareTo(BigDecimal.valueOf(i, 2).add(BigDecimal.ONE).add(new BigDecimal("0.0002"))) <= 0);
            }
        }
    }

    @Test void rejectsEmptyMissingRawAndOutOfRangeScores() {
        assertThrows(IllegalArgumentException.class, () -> mission());
        assertThrows(IllegalArgumentException.class, () -> new MissionInput("M1", null));
        assertThrows(IllegalArgumentException.class, () -> new MissionInput("M1", Arrays.asList(BigDecimal.ONE, null)));
        assertThrows(IllegalArgumentException.class, () -> mission("1.52"));
        assertThrows(IllegalArgumentException.class, () -> mission("-0.01"));
        assertThrows(IllegalArgumentException.class, () -> new MissionInput(" ", List.of(BigDecimal.ONE)));
    }

    @Test void supportsOnlyConfiguredP95OrP99() {
        for (int invalid : List.of(0, 50, 94, 96, 100)) {
            assertThrows(IllegalArgumentException.class, () -> ExplorabilityScorer.scoreMission(mission("0.5"), invalid));
        }
    }

    @Test void roundTripsPublicContractWithDirectPercentileInput() throws Exception {
        var input = ScoringJson.readMission("""
                {"missionId":"M1","product_explore_scores":[0,0.2,0.4,0.6,1]}
                """);
        assertEquals("{\"missionId\":\"M1\",\"explore_score\":0.424}",
                ScoringJson.writeScore(ExplorabilityScorer.scoreMission(input, 95)));
    }

    @Test void rejectsMissingScoresInJsonInsteadOfTreatingThemAsZero() {
        assertThrows(Exception.class, () -> ScoringJson.readMission(
                "{\"missionId\":\"M1\",\"product_explore_scores\":[0.5,null]}"));
    }

    @Test void calculatesRequestedBaselinesFromProductRawScores() {
        var rawScores = Map.of(
                "P1", new BigDecimal("0"),
                "P2", new BigDecimal("1"),
                "P3", new BigDecimal("2"),
                "P4", new BigDecimal("3"),
                "P5", new BigDecimal("4"));
        var baselines = ExplorabilityScorer.calculateBaselines(rawScores, 50, 95, 99);
        assertEquals(0, new BigDecimal("2").compareTo(baselines.get(50)));
        assertEquals(0, new BigDecimal("3.8").compareTo(baselines.get(95)));
        assertEquals(0, new BigDecimal("3.96").compareTo(baselines.get(99)));
    }

    @Test void baselineCalculationRejectsMissingOrInvalidInputs() {
        assertThrows(IllegalArgumentException.class,
                () -> ExplorabilityScorer.calculateBaselines(Map.of(), 95));
        assertThrows(IllegalArgumentException.class,
                () -> ExplorabilityScorer.calculateBaselines(Map.of("P1", new BigDecimal("-1")), 95));
        assertThrows(IllegalArgumentException.class,
                () -> ExplorabilityScorer.calculateBaselines(Map.of("P1", BigDecimal.ONE), 101));
    }
}
