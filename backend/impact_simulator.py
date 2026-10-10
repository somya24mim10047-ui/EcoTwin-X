import os
import pandas as pd
import geopandas as gpd


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SEGMENTS_FILE = os.path.join(
    BASE_DIR, "data", "segments.geojson"
)

INTERVENTIONS_FILE = os.path.join(
    BASE_DIR, "data", "interventions.csv"
)

STOP_RESULTS_FILE = os.path.join(
    BASE_DIR, "output", "heat_stop_optimization.csv"
)

OUTPUT_DIR = os.path.join(
    BASE_DIR, "output"
)

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ============================================================
# SETTINGS
# ============================================================

DEFAULT_STOP_RADIUS_M = 100


# ============================================================
# LOAD INTERVENTIONS
# ============================================================

def load_interventions():

    df = pd.read_csv(INTERVENTIONS_FILE)

    df.columns = [
        str(c).strip().lower().replace(" ", "_")
        for c in df.columns
    ]

    required = [
        "intervention",
        "cost",
        "heat_reduction",
        "pollution_reduction",
        "time_to_benefit_years"
    ]

    for col in required:
        if col not in df.columns:
            raise ValueError(
                f"Missing column in interventions.csv: {col}"
            )

    df["cost"] = pd.to_numeric(
        df["cost"],
        errors="coerce"
    ).fillna(0)

    df["heat_reduction"] = pd.to_numeric(
        df["heat_reduction"],
        errors="coerce"
    ).fillna(0)

    df["pollution_reduction"] = pd.to_numeric(
        df["pollution_reduction"],
        errors="coerce"
    ).fillna(0)

    df["time_to_benefit_years"] = pd.to_numeric(
        df["time_to_benefit_years"],
        errors="coerce"
    ).fillna(0)

    return df


# ============================================================
# LOAD ROAD DATA
# ============================================================

def load_segments():

    segments = gpd.read_file(
        SEGMENTS_FILE
    )

    if segments.empty:
        raise RuntimeError(
            "segments.geojson is empty."
        )

    segments.columns = [
        str(c).strip().lower().replace(" ", "_")
        for c in segments.columns
    ]

    # --------------------------------------------------------
    # MEMBER A CRS FIX
    # --------------------------------------------------------

    if segments.crs is None:

        segments = segments.set_crs(
            "EPSG:3857"
        )

    else:

        bounds = segments.total_bounds

        if (
            abs(bounds[0]) > 180
            or abs(bounds[2]) > 180
            or abs(bounds[1]) > 90
            or abs(bounds[3]) > 90
        ):

            segments = segments.set_crs(
                "EPSG:3857",
                allow_override=True
            )

    # Work in metric CRS
    segments = segments.to_crs(
        "EPSG:3857"
    )

    # Remove bad geometries
    segments = segments[
        segments.geometry.notna()
    ].copy()

    segments = segments[
        ~segments.geometry.is_empty
    ].copy()

    segments = segments[
        segments.geometry.is_valid
    ].copy()

    return segments


# ============================================================
# COLUMN DETECTION
# ============================================================

def get_column(df, names):

    for name in names:

        if name in df.columns:
            return name

    return None


# ============================================================
# BASELINE RISK
# ============================================================

def calculate_baseline_risk(
    shade,
    pollution
):

    heat_dose = 1.0 - shade

    pollution_dose = pollution

    risk = (
        0.7 * heat_dose
        + 0.3 * pollution_dose
    )

    return risk


# ============================================================
# MAIN SIMULATOR
# ============================================================

def main():

    print("\n======================================")
    print("EcoTwin-X Intervention Impact Simulator")
    print("======================================\n")

    # --------------------------------------------------------
    # LOAD
    # --------------------------------------------------------

    segments = load_segments()

    interventions = load_interventions()

    if not os.path.exists(
        STOP_RESULTS_FILE
    ):

        raise FileNotFoundError(
            "Run stop_optimizer.py first.\n"
            f"Missing: {STOP_RESULTS_FILE}"
        )

    stops = pd.read_csv(
        STOP_RESULTS_FILE
    )

    print(
        f"Road segments loaded: {len(segments)}"
    )

    print(
        f"Interventions loaded: {len(interventions)}"
    )

    print(
        f"Optimized stops loaded: {len(stops)}"
    )

    # --------------------------------------------------------
    # SHADE / POLLUTION COLUMNS
    # --------------------------------------------------------

    shade_col = get_column(
        segments,
        [
            "shade_frac",
            "shade_fraction",
            "shade"
        ]
    )

    pollution_col = get_column(
        segments,
        [
            "pollution_proxy",
            "pollution"
        ]
    )

    if shade_col is None:
        raise ValueError(
            "Shade column not found in segments.geojson."
        )

    if pollution_col is None:
        raise ValueError(
            "Pollution column not found in segments.geojson."
        )

    segments["shade_baseline"] = pd.to_numeric(
        segments[shade_col],
        errors="coerce"
    ).fillna(0).clip(0, 1)

    segments["pollution_baseline"] = pd.to_numeric(
        segments[pollution_col],
        errors="coerce"
    ).fillna(0).clip(0)

    # --------------------------------------------------------
    # BASELINE
    # --------------------------------------------------------

    segments["baseline_heat_dose"] = (
        1 - segments["shade_baseline"]
    )

    segments["baseline_pollution_dose"] = (
        segments["pollution_baseline"]
    )

    segments["baseline_risk"] = (
        0.7 * segments["baseline_heat_dose"]
        + 0.3 * segments["baseline_pollution_dose"]
    )

    # --------------------------------------------------------
    # SPATIAL INDEX
    # --------------------------------------------------------

    spatial_index = segments.sindex

    all_results = []

    # --------------------------------------------------------
    # EACH INTERVENTION
    # --------------------------------------------------------

    for _, intervention in interventions.iterrows():

        intervention_name = str(
            intervention["intervention"]
        ).strip()

        cost = float(
            intervention["cost"]
        )

        heat_reduction = float(
            intervention["heat_reduction"]
        )

        pollution_reduction = float(
            intervention["pollution_reduction"]
        )

        benefit_years = float(
            intervention["time_to_benefit_years"]
        )

        print(
            f"\nSimulating: {intervention_name}"
        )

        # ----------------------------------------------------
        # SELECT BEST STOP
        # ----------------------------------------------------

        if (
            intervention_name.lower()
            == "cooling_stop"
        ):

            selected_stops = stops.head(3)

        else:

            selected_stops = stops.head(3)

        if selected_stops.empty:
            continue

        # ----------------------------------------------------
        # SIMULATE EACH SELECTED LOCATION
        # ----------------------------------------------------

        for _, stop in selected_stops.iterrows():

            stop_id = str(
                stop["stop_id"]
            )

            latitude = stop.get(
                "latitude",
                None
            )

            longitude = stop.get(
                "longitude",
                None
            )

            # The optimizer stores projected x/y in these
            # columns after the CRS conversion. Therefore,
            # use the stop's priority result only for selection
            # and locate nearby roads using its rank/ID is not
            # possible directly here.
            #
            # Instead, use the original candidate stop geometry
            # from Member A.

            # ------------------------------------------------
            # Find original stop from candidate file
            # ------------------------------------------------

            candidate_file = os.path.join(
                BASE_DIR,
                "data",
                "candidate_stops_clean.geojson"
            )

            candidates = gpd.read_file(
                candidate_file
            )

            candidates.columns = [
                str(c).strip().lower().replace(" ", "_")
                for c in candidates.columns
            ]

            if candidates.crs is None:
                candidates = candidates.set_crs(
                    "EPSG:4326"
                )

            candidates = candidates.to_crs(
                "EPSG:3857"
            )

            match = candidates[
                candidates["id"].astype(str)
                == stop_id
            ]

            if match.empty:
                continue

            stop_geometry = match.iloc[0].geometry

            # ------------------------------------------------
            # FIND ROADS WITHIN 100M
            # ------------------------------------------------

            search_area = stop_geometry.buffer(
                DEFAULT_STOP_RADIUS_M
            )

            possible = list(
                spatial_index.query(
                    search_area,
                    predicate="intersects"
                )
            )

            if not possible:
                continue

            nearby = segments.iloc[
                possible
            ].copy()

            nearby["distance_to_stop"] = (
                nearby.geometry.distance(
                    stop_geometry
                )
            )

            nearby = nearby[
                nearby["distance_to_stop"]
                <= DEFAULT_STOP_RADIUS_M
            ].copy()

            if nearby.empty:
                continue

            # ------------------------------------------------
            # APPLY INTERVENTION
            # ------------------------------------------------

            nearby["future_heat_dose"] = (
                nearby["baseline_heat_dose"]
                * (1 - heat_reduction)
            )

            nearby["future_pollution_dose"] = (
                nearby["baseline_pollution_dose"]
                * (1 - pollution_reduction)
            )

            nearby["future_risk"] = (
                0.7
                * nearby["future_heat_dose"]
                + 0.3
                * nearby["future_pollution_dose"]
            )

            # ------------------------------------------------
            # METRICS
            # ------------------------------------------------

            baseline_risk = (
                nearby["baseline_risk"].mean()
            )

            future_risk = (
                nearby["future_risk"].mean()
            )

            risk_reduction = (
                baseline_risk
                - future_risk
            )

            percentage_reduction = 0

            if baseline_risk > 0:

                percentage_reduction = (
                    risk_reduction
                    / baseline_risk
                    * 100
                )

            all_results.append({

                "intervention":
                    intervention_name,

                "stop_id":
                    stop_id,

                "cost":
                    cost,

                "time_to_benefit_years":
                    benefit_years,

                "nearby_segments":
                    len(nearby),

                "baseline_risk":
                    baseline_risk,

                "future_risk":
                    future_risk,

                "risk_reduction":
                    risk_reduction,

                "risk_reduction_percent":
                    percentage_reduction,

                "heat_reduction":
                    heat_reduction,

                "pollution_reduction":
                    pollution_reduction
            })

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    if not all_results:

        raise RuntimeError(
            "No intervention results were generated."
        )

    results = pd.DataFrame(
        all_results
    )

    output_file = os.path.join(
        OUTPUT_DIR,
        "intervention_impact.csv"
    )

    results.to_csv(
        output_file,
        index=False
    )

    # --------------------------------------------------------
    # OVERALL SUMMARY
    # --------------------------------------------------------

    summary = (
        results
        .groupby("intervention")
        .agg(
            total_cost=("cost", "sum"),
            average_baseline_risk=(
                "baseline_risk",
                "mean"
            ),
            average_future_risk=(
                "future_risk",
                "mean"
            ),
            average_risk_reduction=(
                "risk_reduction",
                "mean"
            ),
            average_risk_reduction_percent=(
                "risk_reduction_percent",
                "mean"
            )
        )
        .reset_index()
    )

    summary_file = os.path.join(
        OUTPUT_DIR,
        "intervention_overall_impact.csv"
    )

    summary.to_csv(
        summary_file,
        index=False
    )

    # --------------------------------------------------------
    # DISPLAY
    # --------------------------------------------------------

    print("\n======================================")
    print("INTERVENTION IMPACT RESULTS")
    print("======================================\n")

    print(
        results.to_string(index=False)
    )

    print("\n======================================")
    print("OVERALL SUMMARY")
    print("======================================\n")

    print(
        summary.to_string(index=False)
    )

    print(
        f"\nSaved: {output_file}"
    )

    print(
        f"Saved: {summary_file}"
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()