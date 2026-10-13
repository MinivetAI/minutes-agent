package com.minutes.explorability;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.nio.file.Path;
import java.nio.file.Files;
import java.math.BigDecimal;
import java.util.ArrayList;
import org.apache.commons.csv.CSVFormat;
import com.minutes.explorability.ScoringModels.*;

/** JSON inputs/outputs and independently editable CSV normalization baselines. */
public final class ScoringJson {
    private static final ObjectMapper MAPPER = new ObjectMapper();

    private ScoringJson() {}

    public static ScoringConfig readConfig(Path path) throws IOException {
        return required(MAPPER.readValue(path.toFile(), ScoringConfig.class));
    }

    public static ScoringConfig readConfig(String json) throws IOException {
        return required(MAPPER.readValue(json, ScoringConfig.class));
    }

    /** Load independently editable weight and baseline files as one consistent scoring config. */
    public static ScoringConfig readConfig(Path weightsPath, Path baselinesPath) throws IOException {
        ScoringConfig weights = readConfig(weightsPath);
        if (weights.normalization() != null) {
            throw new IllegalArgumentException("Provide baselines either in the weight file or a separate file, not both");
        }
        var normalization = readBaselines(baselinesPath, weights.weightVersion());
        return new ScoringConfig(weights.schemaVersion(), weights.weightVersion(), weights.dimensions(), normalization);
    }

    private static ScoringConfig.Normalization readBaselines(Path path, String weightVersion) throws IOException {
        var format = CSVFormat.DEFAULT.builder().setHeader().setSkipHeaderRecord(true).build();
        var baselines = new ArrayList<ScoringConfig.Baseline>();
        try (var reader = Files.newBufferedReader(path); var rows = format.parse(reader)) {
            for (var row : rows) {
                if (!weightVersion.equals(row.get("weight_version"))) {
                    throw new IllegalArgumentException("Baseline weight_version must match dimension weights");
                }
                baselines.add(new ScoringConfig.Baseline(
                        row.get("analytic_super_category"), new BigDecimal(row.get("p95"))));
            }
        }
        return new ScoringConfig.Normalization(weightVersion, baselines);
    }

    public static MissionInput readMission(String json) throws IOException {
        return required(MAPPER.readValue(json, MissionInput.class));
    }

    public static ProductInput readProduct(String json) throws IOException {
        return required(MAPPER.readValue(json, ProductInput.class));
    }

    public static String writeScore(ProductScore score) throws IOException {
        return MAPPER.writeValueAsString(score);
    }

    public static String writeScore(MissionScore score) throws IOException {
        return MAPPER.writeValueAsString(score);
    }

    private static <T> T required(T value) {
        if (value == null) throw new IllegalArgumentException("JSON input must be an object, not null");
        return value;
    }
}
