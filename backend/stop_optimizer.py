import os
import numpy as np
import pandas as pd
import geopandas as gpd


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SEGMENTS_FILE = os.path.join(BASE_DIR, "data", "segments.geojson")
STOPS_FILE = os.path.join(BASE_DIR, "data", "candidate_stops_clean.geojson")
WORKERS_FILE = os.path.join(BASE_DIR, "data", "worker_profiles.csv")

OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

OUTPUT_FILE = os.path.join(
    OUTPUT_DIR,
    "heat_stop_optimization.csv"
)


# ============================================================
# SETTINGS
# ============================================================

STOP_RADIUS_M = 100

HEAT_WEIGHT = 0.40
POLLUTION_WEIGHT = 0.30
WORKER_WEIGHT = 0.20
ACCESS_WEIGHT = 0.10

VULNERABILITY = {
    "rider": 1.0,
    "vendor": 1.3,
    "child": 1.5
}


# ============================================================
# HELPERS
# ============================================================

def clean_number(series, default=0.0):
    return pd.to_numeric(series, errors="coerce").fillna(default)


def find_column(df, possible_names):
    lookup = {
        str(c).strip().lower().replace(" ", "_"): c
        for c in df.columns
    }

    for name in possible_names:
        key = name.strip().lower().replace(" ", "_")

        if key in lookup:
            return lookup[key]

    return None


# ============================================================
# WORKER PROFILES
# ============================================================

def load_worker_profiles():

    workers = pd.read_csv(WORKERS_FILE)

    workers.columns = [
        str(c).strip().lower().replace(" ", "_")
        for c in workers.columns
    ]

    print(
        "Worker profile columns:",
        list(workers.columns)
    )

    type_col = find_column(
        workers,
        ["worker_type", "type", "archetype"]
    )

    heat_col = find_column(
        workers,
        ["heat_sensitivity", "heat_factor"]
    )

    pollution_col = find_column(
        workers,
        ["pollution_sensitivity", "pollution_factor"]
    )

    if type_col is None:
        raise ValueError(
            "worker_profiles.csv does not contain worker type."
        )

    if heat_col is None:
        raise ValueError(
            "worker_profiles.csv does not contain heat sensitivity."
        )

    if pollution_col is None:
        raise ValueError(
            "worker_profiles.csv does not contain pollution sensitivity."
        )

    workers[heat_col] = clean_number(
        workers[heat_col]
    )

    workers[pollution_col] = clean_number(
        workers[pollution_col]
    )

    profiles = {}

    for _, row in workers.iterrows():

        worker_type = str(
            row[type_col]
        ).strip().lower()

        profiles[worker_type] = {
            "heat_sensitivity": float(
                row[heat_col]
            ),
            "pollution_sensitivity": float(
                row[pollution_col]
            )
        }

    return profiles


# ============================================================
# ROAD SEGMENTS
# ============================================================

def load_segments():

    print("\nLoading road segments...")

    segments = gpd.read_file(
        SEGMENTS_FILE
    )

    print(
        f"Raw road segments: {len(segments)}"
    )

    if segments.empty:
        raise RuntimeError(
            "segments.geojson is empty."
        )

    segments = segments[
        segments.geometry.notna()
    ].copy()

    segments = segments[
        ~segments.geometry.is_empty
    ].copy()

    # --------------------------------------------------------
    # FIX MEMBER A CRS ISSUE
    # --------------------------------------------------------

    if segments.crs is None:

        segments = segments.set_crs(
            "EPSG:3857"
        )

    else:

        bounds = segments.total_bounds

        # If coordinates are larger than valid
        # longitude/latitude ranges, they are already
        # projected coordinates.

        if (
            abs(bounds[0]) > 180
            or abs(bounds[2]) > 180
            or abs(bounds[1]) > 90
            or abs(bounds[3]) > 90
        ):

            print(
                "Detected projected road coordinates."
            )

            print(
                "Correcting road CRS to EPSG:3857."
            )

            segments = segments.set_crs(
                "EPSG:3857",
                allow_override=True
            )

    print(
        f"Corrected road CRS: {segments.crs}"
    )

    # --------------------------------------------------------
    # REMOVE INVALID GEOMETRIES
    # --------------------------------------------------------

    valid_mask = segments.geometry.is_valid

    invalid_count = (
        ~valid_mask
    ).sum()

    if invalid_count > 0:

        print(
            f"Removing {invalid_count} invalid geometries..."
        )

        segments = segments[
            valid_mask
        ].copy()

    # --------------------------------------------------------
    # COLUMN NAMES
    # --------------------------------------------------------

    segments.columns = [
        str(c).strip().lower().replace(" ", "_")
        for c in segments.columns
    ]

    shade_col = find_column(
        segments,
        [
            "shade_frac",
            "shade_fraction",
            "shade"
        ]
    )

    pollution_col = find_column(
        segments,
        [
            "pollution_proxy",
            "pollution"
        ]
    )

    distance_col = find_column(
        segments,
        [
            "distance_m",
            "distance",
            "length_m"
        ]
    )

    if shade_col is None:
        raise ValueError(
            "segments.geojson does not contain shade information."
        )

    if pollution_col is None:
        raise ValueError(
            "segments.geojson does not contain pollution information."
        )

    segments["shade_value"] = (
        clean_number(
            segments[shade_col]
        ).clip(0, 1)
    )

    segments["pollution_value"] = (
        clean_number(
            segments[pollution_col]
        ).clip(0, None)
    )

    # Calculate lengths in meters
    projected = segments.to_crs(
        "EPSG:3857"
    )

    if distance_col is not None:

        segments["distance_value"] = clean_number(
            segments[distance_col]
        )

    else:

        segments["distance_value"] = (
            projected.geometry.length
        )

    print(
        f"Clean road segments: {len(segments)}"
    )

    return segments


# ============================================================
# CANDIDATE STOPS
# ============================================================

def load_candidate_stops():

    print("\nLoading candidate stops...")

    stops = gpd.read_file(
        STOPS_FILE
    )

    print(
        f"Raw candidate stops: {len(stops)}"
    )

    if stops.empty:
        raise RuntimeError(
            "candidate_stops_clean.geojson is empty."
        )

    stops.columns = [
        str(c).strip().lower().replace(" ", "_")
        for c in stops.columns
    ]

    stops = stops[
        stops.geometry.notna()
    ].copy()

    stops = stops[
        ~stops.geometry.is_empty
    ].copy()

    if stops.crs is None:

        stops = stops.set_crs(
            "EPSG:4326"
        )

    # Candidate stops are longitude/latitude,
    # so convert them to meters.

    stops = stops.to_crs(
        "EPSG:3857"
    )

    print(
        f"Stop CRS after projection: {stops.crs}"
    )

    return stops


# ============================================================
# WORKER RISK
# ============================================================

def calculate_worker_risk(
    shade,
    pollution,
    worker_profiles
):

    risks = []

    for worker_type, profile in worker_profiles.items():

        heat_dose = (
            (1 - shade)
            * profile["heat_sensitivity"]
        )

        pollution_dose = (
            pollution
            * profile["pollution_sensitivity"]
        )

        risk = (
            0.7 * heat_dose
            + 0.3 * pollution_dose
        )

        vulnerability = VULNERABILITY.get(
            worker_type,
            1.0
        )

        risk *= vulnerability

        risks.append(risk)

    if not risks:
        return 0.0

    return float(
        np.mean(risks)
    )


# ============================================================
# NORMALIZATION
# ============================================================

def minmax(series):

    series = pd.Series(series)

    minimum = series.min()
    maximum = series.max()

    if (
        pd.isna(minimum)
        or pd.isna(maximum)
        or maximum == minimum
    ):

        return pd.Series(
            np.ones(len(series)),
            index=series.index
        )

    return (
        (series - minimum)
        / (maximum - minimum)
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "\n======================================"
    )

    print(
        "EcoTwin-X Heat Stop Optimizer"
    )

    print(
        "======================================\n"
    )

    # --------------------------------------------------------
    # LOAD
    # --------------------------------------------------------

    segments = load_segments()

    stops = load_candidate_stops()

    worker_profiles = load_worker_profiles()

    print(
        f"\nRoad segments loaded: {len(segments)}"
    )

    print(
        f"Candidate stops loaded: {len(stops)}"
    )

    print(
        f"Worker types: {list(worker_profiles.keys())}"
    )

    # --------------------------------------------------------
    # PROJECT ROAD DATA
    # --------------------------------------------------------

    segments_metric = segments.to_crs(
        "EPSG:3857"
    )

    print(
        "\nUsing projected CRS EPSG:3857."
    )

    # --------------------------------------------------------
    # SPATIAL INDEX
    # --------------------------------------------------------

    spatial_index = segments_metric.sindex

    results = []

    print(
        "\nCalculating candidate stop scores..."
    )

    # --------------------------------------------------------
    # EACH STOP
    # --------------------------------------------------------

    for _, stop in stops.iterrows():

        stop_id = str(
            stop.get(
                "id",
                stop.get(
                    "stop_id",
                    "unknown"
                )
            )
        )

        geometry = stop.geometry

        if (
            geometry is None
            or geometry.is_empty
            or not geometry.is_valid
        ):

            print(
                f"Skipping {stop_id}: invalid geometry"
            )

            continue

        # ----------------------------------------------------
        # 100 METRE SEARCH
        # ----------------------------------------------------

        search_area = geometry.buffer(
            STOP_RADIUS_M
        )

        possible_matches = list(
            spatial_index.query(
                search_area,
                predicate="intersects"
            )
        )

        if not possible_matches:

            print(
                f"Skipping {stop_id}: "
                f"no road segments within "
                f"{STOP_RADIUS_M}m"
            )

            continue

        nearby = segments_metric.iloc[
            possible_matches
        ].copy()

        # ----------------------------------------------------
        # EXACT DISTANCE
        # ----------------------------------------------------

        nearby["distance_to_stop"] = (
            nearby.geometry.distance(
                geometry
            )
        )

        nearby = nearby[
            nearby["distance_to_stop"]
            <= STOP_RADIUS_M
        ].copy()

        if nearby.empty:

            print(
                f"Skipping {stop_id}: "
                f"no road segments within "
                f"{STOP_RADIUS_M}m"
            )

            continue

        # ----------------------------------------------------
        # ENVIRONMENT
        # ----------------------------------------------------

        mean_shade = float(
            nearby["shade_value"].mean()
        )

        mean_pollution = float(
            nearby["pollution_value"].mean()
        )

        worker_risk = calculate_worker_risk(
            mean_shade,
            mean_pollution,
            worker_profiles
        )

        heat_risk = (
            1 - mean_shade
        )

        pollution_risk = (
            mean_pollution
        )

        # More connected nearby roads
        accessibility = min(
            len(nearby) / 10.0,
            1.0
        )

        # ----------------------------------------------------
        # RESULT
        # ----------------------------------------------------

        results.append({

            "stop_id": stop_id,

            "name": stop.get(
                "name",
                ""
            ),

            "stop_type": stop.get(
                "stop_type",
                ""
            ),

            "nearby_road_segments":
                len(nearby),

            "mean_shade":
                mean_shade,

            "mean_pollution":
                mean_pollution,

            "worker_risk":
                worker_risk,

            "heat_risk":
                heat_risk,

            "pollution_risk":
                pollution_risk,

            "accessibility":
                accessibility,

            "latitude":
                geometry.y,

            "longitude":
                geometry.x
        })

    # --------------------------------------------------------
    # CHECK
    # --------------------------------------------------------

    if not results:

        raise RuntimeError(
            "\nNo candidate stops could be evaluated.\n"
            "The road and stop datasets still do not overlap."
        )

    results = pd.DataFrame(
        results
    )

    print(
        f"\nSuccessfully evaluated "
        f"{len(results)} candidate stops."
    )

    # --------------------------------------------------------
    # NORMALIZATION
    # --------------------------------------------------------

    results["worker_risk_norm"] = minmax(
        results["worker_risk"]
    )

    results["heat_risk_norm"] = minmax(
        results["heat_risk"]
    )

    results["pollution_risk_norm"] = minmax(
        results["pollution_risk"]
    )

    results["accessibility_norm"] = minmax(
        results["accessibility"]
    )

    # --------------------------------------------------------
    # PRIORITY SCORE
    # --------------------------------------------------------

    results["priority_score"] = (

        WORKER_WEIGHT
        * results["worker_risk_norm"]

        + HEAT_WEIGHT
        * results["heat_risk_norm"]

        + POLLUTION_WEIGHT
        * results["pollution_risk_norm"]

        + ACCESS_WEIGHT
        * results["accessibility_norm"]
    )

    # --------------------------------------------------------
    # SORT
    # --------------------------------------------------------

    results = results.sort_values(
        "priority_score",
        ascending=False
    ).reset_index(drop=True)

    results["rank"] = (
        results.index + 1
    )

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    results.to_csv(
        OUTPUT_FILE,
        index=False
    )

    # --------------------------------------------------------
    # DISPLAY
    # --------------------------------------------------------

    print(
        "\n======================================"
    )

    print(
        "TOP HEAT STOP LOCATIONS"
    )

    print(
        "======================================\n"
    )

    display_columns = [
        "rank",
        "stop_id",
        "name",
        "stop_type",
        "nearby_road_segments",
        "mean_shade",
        "mean_pollution",
        "worker_risk",
        "priority_score"
    ]

    print(
        results[
            display_columns
        ].head(10).to_string(
            index=False
        )
    )

    print(
        "\nSaved results to:"
    )

    print(
        OUTPUT_FILE
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()