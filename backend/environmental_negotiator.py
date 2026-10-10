import os
import pandas as pd


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INTERVENTIONS_FILE = os.path.join(
    BASE_DIR,
    "data",
    "interventions.csv"
)

IMPACT_FILE = os.path.join(
    BASE_DIR,
    "output",
    "intervention_impact.csv"
)

OUTPUT_DIR = os.path.join(
    BASE_DIR,
    "output"
)

OUTPUT_FILE = os.path.join(
    OUTPUT_DIR,
    "environmental_negotiator.csv"
)


# ============================================================
# NEGOTIATOR
# ============================================================

def main():

    print("\n======================================")
    print("EcoTwin-X Environmental Negotiator")
    print("======================================\n")

    # --------------------------------------------------------
    # LOAD DATA
    # --------------------------------------------------------

    interventions = pd.read_csv(
        INTERVENTIONS_FILE
    )

    impact = pd.read_csv(
        IMPACT_FILE
    )

    interventions.columns = [
        str(c).strip().lower().replace(" ", "_")
        for c in interventions.columns
    ]

    impact.columns = [
        str(c).strip().lower().replace(" ", "_")
        for c in impact.columns
    ]

    # --------------------------------------------------------
    # CLEAN COST DATA
    # --------------------------------------------------------

    interventions["cost"] = pd.to_numeric(
        interventions["cost"],
        errors="coerce"
    ).fillna(0)

    interventions["heat_reduction"] = pd.to_numeric(
        interventions["heat_reduction"],
        errors="coerce"
    ).fillna(0)

    interventions["pollution_reduction"] = pd.to_numeric(
        interventions["pollution_reduction"],
        errors="coerce"
    ).fillna(0)

    # --------------------------------------------------------
    # CLEAN IMPACT DATA
    # --------------------------------------------------------

    impact["cost"] = pd.to_numeric(
        impact["cost"],
        errors="coerce"
    ).fillna(0)

    impact["risk_reduction"] = pd.to_numeric(
        impact["risk_reduction"],
        errors="coerce"
    ).fillna(0)

    impact["risk_reduction_percent"] = pd.to_numeric(
        impact["risk_reduction_percent"],
        errors="coerce"
    ).fillna(0)

    # --------------------------------------------------------
    # AGGREGATE
    # --------------------------------------------------------

    summary = (
        impact
        .groupby("intervention")
        .agg(
            cost=("cost", "mean"),
            baseline_risk=(
                "baseline_risk",
                "mean"
            ),
            future_risk=(
                "future_risk",
                "mean"
            ),
            risk_reduction=(
                "risk_reduction",
                "mean"
            ),
            risk_reduction_percent=(
                "risk_reduction_percent",
                "mean"
            ),
            locations_evaluated=(
                "stop_id",
                "nunique"
            )
        )
        .reset_index()
    )

    # --------------------------------------------------------
    # MERGE ASSUMPTIONS
    # --------------------------------------------------------

    summary = summary.merge(
        interventions[
            [
                "intervention",
                "heat_reduction",
                "pollution_reduction",
                "time_to_benefit_years"
            ]
        ],
        on="intervention",
        how="left"
    )

    # --------------------------------------------------------
    # COST EFFECTIVENESS
    # --------------------------------------------------------

    summary["risk_reduction_per_lakh"] = 0.0

    valid_cost = summary["cost"] > 0

    summary.loc[
        valid_cost,
        "risk_reduction_per_lakh"
    ] = (
        summary.loc[
            valid_cost,
            "risk_reduction"
        ]
        / summary.loc[
            valid_cost,
            "cost"
        ]
        * 100000
    )

    # --------------------------------------------------------
    # NEGOTIATOR SCORE
    # --------------------------------------------------------

    def normalize(series):

        minimum = series.min()
        maximum = series.max()

        if maximum == minimum:
            return pd.Series(
                1.0,
                index=series.index
            )

        return (
            (series - minimum)
            / (maximum - minimum)
        )

    summary["impact_score"] = normalize(
        summary["risk_reduction"]
    )

    summary["cost_efficiency_score"] = normalize(
        summary["risk_reduction_per_lakh"]
    )

    # Faster intervention = better
    summary["speed_score"] = 1 - normalize(
        summary["time_to_benefit_years"]
    )

    summary["negotiator_score"] = (
        0.50 * summary["impact_score"]
        + 0.30 * summary["cost_efficiency_score"]
        + 0.20 * summary["speed_score"]
    )

    # --------------------------------------------------------
    # RANK
    # --------------------------------------------------------

    summary = summary.sort_values(
        "negotiator_score",
        ascending=False
    ).reset_index(drop=True)

    summary["rank"] = (
        summary.index + 1
    )

    # --------------------------------------------------------
    # RECOMMENDATION
    # --------------------------------------------------------

    summary["recommendation"] = "Consider"

    if len(summary) > 0:

        summary.loc[
            summary.index[0],
            "recommendation"
        ] = "Recommended"

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    summary.to_csv(
        OUTPUT_FILE,
        index=False
    )

    # --------------------------------------------------------
    # DISPLAY
    # --------------------------------------------------------

    print("Environmental Negotiator Results:\n")

    display_columns = [
        "rank",
        "intervention",
        "cost",
        "risk_reduction",
        "risk_reduction_percent",
        "time_to_benefit_years",
        "negotiator_score",
        "recommendation"
    ]

    print(
        summary[
            display_columns
        ].to_string(index=False)
    )

    print(
        f"\nSaved to:"
    )

    print(
        OUTPUT_FILE
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()