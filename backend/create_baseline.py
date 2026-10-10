import geopandas as gpd
import pandas as pd

from exposure import calculate_exposure


# -----------------------------
# 1. File locations
# -----------------------------

INPUT_FILE = "../data/segments.geojson"
OUTPUT_FILE = "../output/baseline_results.csv"
SUMMARY_FILE = "../output/baseline_summary.csv"


# -----------------------------
# 2. Load road segments
# -----------------------------

gdf = gpd.read_file(INPUT_FILE)

print("Loaded segments:", len(gdf))


# -----------------------------
# 3. Check required columns
# -----------------------------

required_columns = [
    "edge_id",
    "u",
    "v",
    "hour",
    "shade_frac",
    "pollution_proxy"
]

for column in required_columns:
    if column not in gdf.columns:
        raise ValueError(f"Missing column: {column}")


# -----------------------------
# 4. Calculate baseline exposure
# -----------------------------

HEAT_FACTOR = 0.80

baseline = calculate_exposure(
    gdf,
    HEAT_FACTOR
)


# -----------------------------
# 5. Save individual results
# -----------------------------

baseline[
    [
        "edge_id",
        "u",
        "v",
        "hour",
        "shade_frac",
        "pollution_proxy",
        "heat_factor",
        "exposure"
    ]
].to_csv(
    OUTPUT_FILE,
    index=False
)


# -----------------------------
# 6. Create hourly summary
# -----------------------------

summary = (
    baseline
    .groupby("hour")
    .agg(
        average_shade=("shade_frac", "mean"),
        average_pollution=("pollution_proxy", "mean"),
        average_exposure=("exposure", "mean"),
        maximum_exposure=("exposure", "max"),
        road_segments=("edge_id", "count")
    )
    .reset_index()
)


# -----------------------------
# 7. Save summary
# -----------------------------

summary.to_csv(
    SUMMARY_FILE,
    index=False
)


# -----------------------------
# 8. Display results
# -----------------------------

print("\nBaseline Exposure Results:")
print(
    baseline[
        [
            "edge_id",
            "hour",
            "shade_frac",
            "pollution_proxy",
            "heat_factor",
            "exposure"
        ]
    ]
)

print("\nHourly Summary:")
print(summary)

print("\nBaseline calculation completed!")