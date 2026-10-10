import os
import pandas as pd


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

OUTPUT_DIR = os.path.join(BASE_DIR, "output")

ROUTING_FILE = os.path.join(
    OUTPUT_DIR,
    "routing_engine_results.csv"
)

IMPACT_FILE = os.path.join(
    OUTPUT_DIR,
    "intervention_impact.csv"
)

NEGOTIATOR_FILE = os.path.join(
    OUTPUT_DIR,
    "environmental_negotiator.csv"
)

BUDGET_FILE = os.path.join(
    OUTPUT_DIR,
    "budget_optimization.csv"
)

VALIDATION_FILE = os.path.join(
    OUTPUT_DIR,
    "validation_report.csv"
)


# ============================================================
# HELPER
# ============================================================

def load_csv(path):
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return None

    try:
        return pd.read_csv(path)
    except Exception as e:
        print(f"Could not read {path}")
        print(f"Error: {e}")
        return None


# ============================================================
# VALIDATE ROUTING RESULTS
# ============================================================

def validate_routing():

    df = load_csv(ROUTING_FILE)

    if df is None or df.empty:
        return {
            "module": "routing_engine",
            "status": "FAILED",
            "check": "routing output exists",
            "result": "No routing results found"
        }

    required_columns = [
        "worker_type"
    ]

    missing = [
        col for col in required_columns
        if col not in df.columns
    ]

    if missing:
        return {
            "module": "routing_engine",
            "status": "FAILED",
            "check": "required columns",
            "result": f"Missing columns: {missing}"
        }

    return {
        "module": "routing_engine",
        "status": "PASSED",
        "check": "routing output",
        "result": f"{len(df)} routing records found"
    }


# ============================================================
# VALIDATE IMPACT SIMULATOR
# ============================================================

def validate_impact():

    df = load_csv(IMPACT_FILE)

    if df is None or df.empty:
        return {
            "module": "impact_simulator",
            "status": "FAILED",
            "check": "impact output exists",
            "result": "No intervention impact results found"
        }

    required_columns = [
        "intervention"
    ]

    missing = [
        col for col in required_columns
        if col not in df.columns
    ]

    if missing:
        return {
            "module": "impact_simulator",
            "status": "FAILED",
            "check": "required columns",
            "result": f"Missing columns: {missing}"
        }

    return {
        "module": "impact_simulator",
        "status": "PASSED",
        "check": "impact output",
        "result": f"{len(df)} intervention impact records found"
    }


# ============================================================
# VALIDATE ENVIRONMENTAL NEGOTIATOR
# ============================================================

def validate_negotiator():

    df = load_csv(NEGOTIATOR_FILE)

    if df is None or df.empty:
        return {
            "module": "environmental_negotiator",
            "status": "FAILED",
            "check": "negotiator output exists",
            "result": "No negotiator results found"
        }

    if "intervention" not in df.columns:
        return {
            "module": "environmental_negotiator",
            "status": "FAILED",
            "check": "intervention column",
            "result": "Intervention column missing"
        }

    return {
        "module": "environmental_negotiator",
        "status": "PASSED",
        "check": "negotiator output",
        "result": f"{len(df)} intervention options ranked"
    }


# ============================================================
# VALIDATE BUDGET OPTIMIZER
# ============================================================

def validate_budget():

    df = load_csv(BUDGET_FILE)

    if df is None or df.empty:
        return {
            "module": "budget_optimizer",
            "status": "FAILED",
            "check": "budget output exists",
            "result": "No budget optimization results found"
        }

    required_columns = [
        "total_cost",
        "overall_impact"
    ]

    missing = [
        col for col in required_columns
        if col not in df.columns
    ]

    if missing:
        return {
            "module": "budget_optimizer",
            "status": "FAILED",
            "check": "budget columns",
            "result": f"Missing columns: {missing}"
        }

    # Check whether selected solutions exceed budget
    budget = 500000

    invalid = (
        pd.to_numeric(
            df["total_cost"],
            errors="coerce"
        ) > budget
    ).sum()

    if invalid > 0:
        return {
            "module": "budget_optimizer",
            "status": "FAILED",
            "check": "budget constraint",
            "result": f"{invalid} solutions exceed ₹{budget:,}"
        }

    return {
        "module": "budget_optimizer",
        "status": "PASSED",
        "check": "budget constraint",
        "result": f"{len(df)} valid budget solutions"
    }


# ============================================================
# CROSS-MODULE VALIDATION
# ============================================================

def cross_validate():

    impact = load_csv(IMPACT_FILE)
    negotiator = load_csv(NEGOTIATOR_FILE)
    budget = load_csv(BUDGET_FILE)

    checks = []

    # --------------------------------------------------------
    # Intervention consistency
    # --------------------------------------------------------

    if (
        impact is not None
        and not impact.empty
        and negotiator is not None
        and not negotiator.empty
    ):

        if (
            "intervention" in impact.columns
            and "intervention" in negotiator.columns
        ):

            impact_types = set(
                impact["intervention"]
                .dropna()
                .astype(str)
            )

            negotiator_types = set(
                negotiator["intervention"]
                .dropna()
                .astype(str)
            )

            common = (
                impact_types
                .intersection(negotiator_types)
            )

            checks.append({
                "module": "cross_validation",
                "status": (
                    "PASSED"
                    if common
                    else "WARNING"
                ),
                "check": "intervention consistency",
                "result": (
                    f"{len(common)} common intervention types"
                )
            })

    # --------------------------------------------------------
    # Budget consistency
    # --------------------------------------------------------

    if (
        budget is not None
        and not budget.empty
        and "total_cost" in budget.columns
    ):

        budget_values = pd.to_numeric(
            budget["total_cost"],
            errors="coerce"
        )

        if (budget_values <= 500000).all():

            checks.append({
                "module": "cross_validation",
                "status": "PASSED",
                "check": "budget consistency",
                "result": "All selected plans within budget"
            })

        else:

            checks.append({
                "module": "cross_validation",
                "status": "FAILED",
                "check": "budget consistency",
                "result": "Some plans exceed budget"
            })

    return checks


# ============================================================
# MAIN VALIDATION
# ============================================================

def main():

    print("\n================================")
    print(" EcoTwin-X Validation")
    print("================================\n")

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True
    )

    results = []

    # Individual modules
    results.append(
        validate_routing()
    )

    results.append(
        validate_impact()
    )

    results.append(
        validate_negotiator()
    )

    results.append(
        validate_budget()
    )

    # Cross-module checks
    results.extend(
        cross_validate()
    )

    validation_df = pd.DataFrame(
        results
    )

    validation_df.to_csv(
        VALIDATION_FILE,
        index=False
    )

    print(
        validation_df.to_string(
            index=False
        )
    )

    print(
        "\n================================"
    )
    print(
        " VALIDATION COMPLETE"
    )
    print(
        "================================"
    )

    passed = (
        validation_df["status"]
        == "PASSED"
    ).sum()

    failed = (
        validation_df["status"]
        == "FAILED"
    ).sum()

    warnings = (
        validation_df["status"]
        == "WARNING"
    ).sum()

    print(f"\nPassed : {passed}")
    print(f"Failed : {failed}")
    print(f"Warning: {warnings}")

    print(
        f"\nValidation report saved to:\n"
        f"{VALIDATION_FILE}"
    )


if __name__ == "__main__":
    main()