import os
import pandas as pd


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

OUTPUT_DIR = os.path.join(BASE_DIR, "output")

IMPACT_FILE = os.path.join(
    OUTPUT_DIR,
    "intervention_impact.csv"
)

OVERALL_IMPACT_FILE = os.path.join(
    OUTPUT_DIR,
    "intervention_overall_impact.csv"
)

NEGOTIATOR_FILE = os.path.join(
    OUTPUT_DIR,
    "environmental_negotiator.csv"
)

BUDGET_FILE = os.path.join(
    OUTPUT_DIR,
    "budget_optimization.csv"
)

WORKER_OUTPUT = os.path.join(
    OUTPUT_DIR,
    "worker_comparison.csv"
)

OVERALL_OUTPUT = os.path.join(
    OUTPUT_DIR,
    "comparison_metrics.csv"
)


# ============================================================
# LOAD DATA
# ============================================================

def load_file(path):
    if not os.path.exists(path):
        print(f"Warning: file not found: {path}")
        return None

    return pd.read_csv(path)


# ============================================================
# WORKER-LEVEL COMPARISON
# ============================================================

def create_worker_comparison(df):
    if df is None or df.empty:
        return pd.DataFrame()

    numeric_columns = [
        "baseline_heat",
        "baseline_pollution",
        "baseline_risk",
        "future_heat",
        "future_pollution",
        "future_risk"
    ]

    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            )

    # If impact_simulator uses slightly different names,
    # try to identify them automatically.
    column_map = {}

    possible_columns = {
        "baseline_heat": [
            "baseline_heat",
            "heat_baseline"
        ],
        "baseline_pollution": [
            "baseline_pollution",
            "pollution_baseline"
        ],
        "baseline_risk": [
            "baseline_risk",
            "risk_baseline"
        ],
        "future_heat": [
            "future_heat",
            "heat_future"
        ],
        "future_pollution": [
            "future_pollution",
            "pollution_future"
        ],
        "future_risk": [
            "future_risk",
            "risk_future"
        ]
    }

    for standard_name, candidates in possible_columns.items():
        for candidate in candidates:
            if candidate in df.columns:
                column_map[standard_name] = candidate
                break

    # Create standard columns
    for standard_name, source_name in column_map.items():
        if standard_name not in df.columns:
            df[standard_name] = df[source_name]

    required = [
        "baseline_risk",
        "future_risk"
    ]

    if not all(col in df.columns for col in required):
        print(
            "Warning: worker-level risk columns were not found."
        )
        return pd.DataFrame()

    df["risk_reduction"] = (
        df["baseline_risk"]
        - df["future_risk"]
    )

    df["risk_reduction_percent"] = 0.0

    mask = df["baseline_risk"] != 0

    df.loc[mask, "risk_reduction_percent"] = (
        df.loc[mask, "risk_reduction"]
        / df.loc[mask, "baseline_risk"]
        * 100
    )

    return df


# ============================================================
# INTERVENTION-LEVEL COMPARISON
# ============================================================

def create_intervention_comparison(df):
    if df is None or df.empty:
        return pd.DataFrame()

    # Try to identify intervention column
    intervention_col = None

    for col in [
        "intervention",
        "intervention_type",
        "type"
    ]:
        if col in df.columns:
            intervention_col = col
            break

    if intervention_col is None:
        print(
            "Warning: intervention column not found."
        )
        return pd.DataFrame()

    # Identify baseline/future risk columns
    baseline_col = None
    future_col = None

    for col in [
        "baseline_risk",
        "risk_baseline"
    ]:
        if col in df.columns:
            baseline_col = col
            break

    for col in [
        "future_risk",
        "risk_future"
    ]:
        if col in df.columns:
            future_col = col
            break

    if baseline_col is None or future_col is None:
        print(
            "Warning: baseline/future risk columns "
            "not found in intervention data."
        )
        return pd.DataFrame()

    df[baseline_col] = pd.to_numeric(
        df[baseline_col],
        errors="coerce"
    )

    df[future_col] = pd.to_numeric(
        df[future_col],
        errors="coerce"
    )

    grouped = (
        df.groupby(intervention_col)
        .agg(
            baseline_risk=(
                baseline_col,
                "mean"
            ),
            future_risk=(
                future_col,
                "mean"
            ),
            number_of_cases=(
                baseline_col,
                "count"
            )
        )
        .reset_index()
    )

    grouped["risk_reduction"] = (
        grouped["baseline_risk"]
        - grouped["future_risk"]
    )

    grouped["risk_reduction_percent"] = 0.0

    mask = grouped["baseline_risk"] != 0

    grouped.loc[
        mask,
        "risk_reduction_percent"
    ] = (
        grouped.loc[
            mask,
            "risk_reduction"
        ]
        / grouped.loc[
            mask,
            "baseline_risk"
        ]
        * 100
    )

    grouped = grouped.rename(
        columns={
            intervention_col: "intervention"
        }
    )

    return grouped


# ============================================================
# NEGOTIATOR INFORMATION
# ============================================================

def add_negotiator_information(df):
    if df.empty:
        return df

    negotiator = load_file(
        NEGOTIATOR_FILE
    )

    if negotiator is None or negotiator.empty:
        return df

    if "intervention" not in negotiator.columns:
        return df

    useful_columns = [
        "intervention",
        "negotiator_score",
        "recommendation"
    ]

    useful_columns = [
        col for col in useful_columns
        if col in negotiator.columns
    ]

    if len(useful_columns) <= 1:
        return df

    negotiator = negotiator[
        useful_columns
    ].drop_duplicates(
        subset=["intervention"]
    )

    return df.merge(
        negotiator,
        on="intervention",
        how="left"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n==============================")
    print(" EcoTwin-X Comparison Metrics")
    print("==============================\n")

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Worker comparison
    # --------------------------------------------------------

    impact_df = load_file(
        IMPACT_FILE
    )

    worker_comparison = create_worker_comparison(
        impact_df
    )

    if not worker_comparison.empty:

        worker_comparison.to_csv(
            WORKER_OUTPUT,
            index=False
        )

        print(
            f"Worker comparison saved to:\n"
            f"{WORKER_OUTPUT}"
        )

    else:

        print(
            "Worker comparison could not be generated."
        )

    # --------------------------------------------------------
    # Intervention comparison
    # --------------------------------------------------------

    intervention_comparison = (
        create_intervention_comparison(
            impact_df
        )
    )

    if not intervention_comparison.empty:

        intervention_comparison = (
            add_negotiator_information(
                intervention_comparison
            )
        )

        intervention_comparison.to_csv(
            OVERALL_OUTPUT,
            index=False
        )

        print(
            f"\nOverall comparison saved to:\n"
            f"{OVERALL_OUTPUT}"
        )

        print(
            "\n=============================="
        )
        print(
            " INTERVENTION COMPARISON"
        )
        print(
            "=============================="
        )

        print(
            intervention_comparison.to_string(
                index=False
            )
        )

    else:

        print(
            "\nIntervention comparison "
            "could not be generated."
        )

    # --------------------------------------------------------
    # Budget information
    # --------------------------------------------------------

    budget_df = load_file(
        BUDGET_FILE
    )

    if budget_df is not None and not budget_df.empty:

        print(
            "\n=============================="
        )
        print(
            " BEST BUDGET PLAN"
        )
        print(
            "=============================="
        )

        best = budget_df.iloc[0]

        if "interventions" in best:
            print(
                f"Plan: {best['interventions']}"
            )

        if "total_cost" in best:
            print(
                f"Cost: ₹{float(best['total_cost']):,.0f}"
            )

        if "overall_impact" in best:
            print(
                f"Overall impact: "
                f"{float(best['overall_impact']):.4f}"
            )

    print(
        "\nComparison metrics completed."
    )


if __name__ == "__main__":
    main()