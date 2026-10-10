import os
import itertools
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INTERVENTION_FILE = os.path.join(
    BASE_DIR, "data", "interventions.csv"
)

OUTPUT_DIR = os.path.join(BASE_DIR, "output")
OUTPUT_FILE = os.path.join(
    OUTPUT_DIR, "budget_optimization.csv"
)

# Available budget in rupees
BUDGET = 500000


# ============================================================
# LOAD INTERVENTIONS
# ============================================================

def load_interventions():
    if not os.path.exists(INTERVENTION_FILE):
        raise FileNotFoundError(
            f"Intervention file not found:\n{INTERVENTION_FILE}"
        )

    df = pd.read_csv(INTERVENTION_FILE)

    required_columns = [
        "intervention",
        "cost",
        "heat_reduction",
        "pollution_reduction",
        "time_to_benefit_years"
    ]

    missing = [
        col for col in required_columns
        if col not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing columns in interventions.csv: {missing}"
        )

    # Make sure numeric columns are actually numeric
    for col in required_columns[1:]:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    df = df.dropna(
        subset=[
            "intervention",
            "cost",
            "heat_reduction",
            "pollution_reduction",
            "time_to_benefit_years"
        ]
    )

    return df


# ============================================================
# CALCULATE INTERVENTION IMPACT
# ============================================================

def calculate_combination_impact(combination, intervention_df):

    total_cost = 0
    total_heat_reduction = 0
    total_pollution_reduction = 0
    total_impact = 0
    total_time = 0

    selected = []

    for intervention_name, quantity in combination.items():

        row = intervention_df[
            intervention_df["intervention"] == intervention_name
        ]

        if row.empty:
            continue

        row = row.iloc[0]

        cost = float(row["cost"])
        heat = float(row["heat_reduction"])
        pollution = float(row["pollution_reduction"])
        time = float(row["time_to_benefit_years"])

        total_cost += cost * quantity

        # Impact per intervention
        intervention_impact = (
            heat * 0.60 +
            pollution * 0.40
        )

        total_heat_reduction += (
            heat * quantity
        )

        total_pollution_reduction += (
            pollution * quantity
        )

        total_impact += (
            intervention_impact * quantity
        )

        if quantity > 0:
            total_time += time * quantity

            selected.append(
                f"{intervention_name} x{quantity}"
            )

    if total_cost > BUDGET:
        return None

    if total_cost == 0:
        return None

    return {
        "interventions": " + ".join(selected),
        "cooling_stops": combination.get(
            "cooling_stop", 0
        ),
        "trees": combination.get(
            "trees", 0
        ),
        "green_corridors": combination.get(
            "green_corridor", 0
        ),
        "total_cost": total_cost,
        "remaining_budget": BUDGET - total_cost,
        "heat_reduction": total_heat_reduction,
        "pollution_reduction": total_pollution_reduction,
        "overall_impact": total_impact,
        "time_to_benefit": total_time
    }


# ============================================================
# FIND BEST BUDGET COMBINATIONS
# ============================================================

def optimize_budget(intervention_df):

    names = intervention_df["intervention"].tolist()

    combinations = []

    # Maximum quantities are kept bounded so that
    # the search remains fast.
    max_quantity = 10

    for quantities in itertools.product(
        range(max_quantity + 1),
        repeat=len(names)
    ):

        # Skip empty combination
        if all(q == 0 for q in quantities):
            continue

        combination = dict(
            zip(names, quantities)
        )

        result = calculate_combination_impact(
            combination,
            intervention_df
        )

        if result is not None:
            combinations.append(result)

    return pd.DataFrame(combinations)


# ============================================================
# RANK SOLUTIONS
# ============================================================

def rank_solutions(df):

    if df.empty:
        return df

    # Normalize impact
    max_impact = df["overall_impact"].max()

    if max_impact > 0:
        df["impact_score"] = (
            df["overall_impact"] /
            max_impact
        )
    else:
        df["impact_score"] = 0

    # Cost efficiency
    df["cost_efficiency"] = (
        df["overall_impact"] /
        df["total_cost"]
    )

    max_efficiency = df["cost_efficiency"].max()

    if max_efficiency > 0:
        df["cost_efficiency_score"] = (
            df["cost_efficiency"] /
            max_efficiency
        )
    else:
        df["cost_efficiency_score"] = 0

    # Faster interventions are preferred
    max_time = df["time_to_benefit"].max()

    if max_time > 0:
        df["speed_score"] = (
            1 -
            df["time_to_benefit"] /
            max_time
        )
    else:
        df["speed_score"] = 1

    # Final budget score
    df["budget_score"] = (
        0.50 * df["impact_score"]
        + 0.30 * df["cost_efficiency_score"]
        + 0.20 * df["speed_score"]
    )

    df = df.sort_values(
        "budget_score",
        ascending=False
    ).reset_index(drop=True)

    df["rank"] = range(1, len(df) + 1)

    df["recommendation"] = "Alternative"

    if len(df) > 0:
        df.loc[
            df.index[0],
            "recommendation"
        ] = "Recommended"

    return df


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n==============================")
    print(" EcoTwin-X Budget Optimizer")
    print("==============================\n")

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True
    )

    intervention_df = load_interventions()

    print("Interventions loaded:")
    print(
        intervention_df[
            [
                "intervention",
                "cost",
                "heat_reduction",
                "pollution_reduction",
                "time_to_benefit_years"
            ]
        ].to_string(index=False)
    )

    print(f"\nAvailable budget: ₹{BUDGET:,}")

    results = optimize_budget(
        intervention_df
    )

    if results.empty:
        print("\nNo valid intervention combination found.")
        return

    results = rank_solutions(results)

    results.to_csv(
        OUTPUT_FILE,
        index=False
    )

    print("\n==============================")
    print(" BEST BUDGET PLAN")
    print("==============================")

    best = results.iloc[0]

    print(
        f"Plan: {best['interventions']}"
    )

    print(
        f"Cost: ₹{best['total_cost']:,.0f}"
    )

    print(
        f"Remaining budget: "
        f"₹{best['remaining_budget']:,.0f}"
    )

    print(
        f"Heat reduction: "
        f"{best['heat_reduction']:.2f}"
    )

    print(
        f"Pollution reduction: "
        f"{best['pollution_reduction']:.2f}"
    )

    print(
        f"Overall impact: "
        f"{best['overall_impact']:.4f}"
    )

    print(
        f"Budget score: "
        f"{best['budget_score']:.4f}"
    )

    print(
        f"\nOutput saved to:\n{OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()