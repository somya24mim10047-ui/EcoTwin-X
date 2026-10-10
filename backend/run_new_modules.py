import os
import subprocess
import sys


# ============================================================
# PATH
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)


# ============================================================
# MODULES
# ============================================================

MODULES = [
    "routing_engine.py",
    "stop_optimizer.py",
    "impact_simulator.py",
    "environmental_negotiator.py",
    "budget_optimizer.py",
    "comparison_metrics.py",
    "validation.py"
]


# ============================================================
# RUN MODULE
# ============================================================

def run_module(module):

    print("\n" + "=" * 60)
    print(f"RUNNING: {module}")
    print("=" * 60)

    result = subprocess.run(
        [sys.executable, module],
        cwd=BASE_DIR
    )

    if result.returncode != 0:

        print(
            f"\n❌ {module} FAILED"
        )

        return False

    print(
        f"\n✅ {module} COMPLETED"
    )

    return True


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n")
    print("=" * 60)
    print("        ECOTWIN-X MEMBER B PIPELINE")
    print("=" * 60)

    failed_modules = []

    for module in MODULES:

        module_path = os.path.join(
            BASE_DIR,
            module
        )

        if not os.path.exists(module_path):

            print(
                f"\n⚠️ File not found: {module}"
            )

            failed_modules.append(
                module
            )

            continue

        success = run_module(
            module
        )

        if not success:

            failed_modules.append(
                module
            )

            print(
                "\nPipeline stopped because "
                "this module failed."
            )

            break

    # ========================================================
    # FINAL RESULT
    # ========================================================

    print("\n")
    print("=" * 60)
    print("              PIPELINE SUMMARY")
    print("=" * 60)

    if not failed_modules:

        print(
            "\n🎉 ALL MEMBER B MODULES COMPLETED SUCCESSFULLY!"
        )

        print(
            "\nGenerated outputs are available in:"
        )

        print(
            os.path.join(
                BASE_DIR,
                "..",
                "output"
            )
        )

    else:

        print(
            "\n❌ Pipeline did not complete."
        )

        print(
            "\nFailed module(s):"
        )

        for module in failed_modules:
            print(
                f"  - {module}"
            )


if __name__ == "__main__":
    main()