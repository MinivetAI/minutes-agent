package com.minutes.explorability;

import com.minutes.explorability.ScoringModels.*;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.stream.IntStream;
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

    @Test void averagesEveryProductWhenMissionHasFewerThanFifty() {
        assertScore("0.44", ExplorabilityScorer.scoreMission(mission("0", "0.2", "0.4", "0.6", "1")));
    }

    @Test void averagesOnlyTopFiftyProducts() {
        var scores = new ArrayList<BigDecimal>();
        scores.add(BigDecimal.ZERO);
        IntStream.range(0, 50).forEach(i -> scores.add(BigDecimal.ONE));
        assertScore("1", ExplorabilityScorer.scoreMission(new MissionInput("M1", scores)));
    }

    @Test void selectsTheHighestFiftyFromARealisticLargerMission() {
        var scores = IntStream.rangeClosed(1, 100)
                .mapToObj(i -> BigDecimal.valueOf(i, 2))
                .toList();
        assertScore("0.755", ExplorabilityScorer.scoreMission(new MissionInput("M1", scores)));
    }

    @Test void singleProductKeepsItsScore() {
        assertScore("0.37", ExplorabilityScorer.scoreMission(mission("0.37")));
    }

    @Test void zeroAndIdenticalScoreMissionsAreHandled() {
        assertScore("0", ExplorabilityScorer.scoreMission(mission("0", "0", "0")));
        assertScore("1", ExplorabilityScorer.scoreMission(mission("1", "1")));
        assertScore("0.4", ExplorabilityScorer.scoreMission(mission("0.4", "0.4", "0.4")));
    }

    @Test void roundsTheAverageToFourDecimalPlaces() {
        assertScore("0.3333", ExplorabilityScorer.scoreMission(mission("0", "0", "1")));
        assertScore("0.6667", ExplorabilityScorer.scoreMission(mission("0", "1", "1")));
    }

    @Test void scoreOrderDoesNotChangeResultOrMutateCallerList() {
        var values = new ArrayList<>(mission("0.2", "0", "0.4", "1", "0.6").productExploreScores());
        var input = new MissionInput("M1", values);
        var before = List.copyOf(values);
        var result = ExplorabilityScorer.scoreMission(input);
        assertEquals(before, values);
        Collections.reverse(values);
        assertEquals(result, ExplorabilityScorer.scoreMission(new MissionInput("M1", values)));
        values.clear();
        assertEquals(result, ExplorabilityScorer.scoreMission(input));
    }

    @Test void resultAlwaysStaysInNormalizedRange() {
        for (int i = 0; i <= 100; i++) {
            var input = new MissionInput("M1", List.of(
                    BigDecimal.ZERO, BigDecimal.valueOf(i, 2), BigDecimal.ONE));
            BigDecimal result = ExplorabilityScorer.scoreMission(input).exploreScore();
            assertTrue(result.signum() >= 0 && result.compareTo(BigDecimal.ONE) <= 0);
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

    @Test void roundTripsPublicContract() throws Exception {
        var input = ScoringJson.readMission("""
                {"missionId":"M1","product_explore_scores":[0,0.2,0.4,0.6,1]}
                """);
        assertEquals("{\"missionId\":\"M1\",\"explore_score\":0.44}",
                ScoringJson.writeScore(ExplorabilityScorer.scoreMission(input)));
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
