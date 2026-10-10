import subprocess
import sys


def run_script(script_name):
    print("\n" + "=" * 50)
    print(f"RUNNING: {script_name}")
    print("=" * 50)

    result = subprocess.run(
        [sys.executable, script_name],
        check=False
    )

    if result.returncode != 0:
        print(f"\nERROR: {script_name} failed.")
        return False

    print(f"\n{script_name} completed successfully.")
    return True


if __name__ == "__main__":

    scripts = [
        "routing.py",
        "ranking.py",
        "validation.py"
    ]

    print("\n==========================================")
    print("       ECO TWIN X COOL PATH")
    print("          MEMBER B BACKEND")
    print("==========================================")

    for script in scripts:

        success = run_script(script)

        if not success:
            print("\nBackend stopped because of an error.")
            sys.exit(1)

    print("\n==========================================")
    print("       MEMBER B BACKEND COMPLETE")
    print("==========================================")

    print("\nGenerated outputs:")

    print("✓ routes_9.json")
    print("✓ routes_11.json")
    print("✓ routes_13.json")
    print("✓ routes_15.json")
    print("✓ routes_17.json")
    print("✓ priority_top10.csv")
    print("✓ validation_results.csv")

    print("\nAll Member B modules completed successfully.")