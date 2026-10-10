import pandas as pd
import os


def calculate_risk(data):
    """
    Calculate risk using:

    Risk = Exposure × Vulnerability
    """

    data = data.copy()

    data["risk"] = (
        data["exposure"] *
        data["vulnerability"]
    )

    return data


def rank_locations(data):
    """
    Rank locations from highest risk to lowest risk.
    """

    data = data.sort_values(
        by="risk",
        ascending=False
    ).reset_index(drop=True)

    data["rank"] = data.index + 1

    return data


def get_top_10(data):
    """
    Select the 10 highest-risk locations.
    """

    return data.head(10)


if __name__ == "__main__":

    # ------------------------------------------------
    # TEMPORARY DUMMY DATA
    # Later this will come from the real project data.
    # ------------------------------------------------

    data = pd.DataFrame({

        "location_id": [
            "L01", "L02", "L03", "L04", "L05",
            "L06", "L07", "L08", "L09", "L10",
            "L11", "L12"
        ],

        "latitude": [
            12.9700, 12.9710, 12.9720, 12.9730,
            12.9740, 12.9750, 12.9760, 12.9770,
            12.9780, 12.9790, 12.9800, 12.9810
        ],

        "longitude": [
            77.5900, 77.5910, 77.5920, 77.5930,
            77.5940, 77.5950, 77.5960, 77.5970,
            77.5980, 77.5990, 77.6000, 77.6010
        ],

        "exposure": [
            0.80, 0.65, 0.90, 0.40,
            0.75, 0.55, 0.95, 0.60,
            0.85, 0.45, 0.70, 0.88
        ],

        "vulnerability": [
            0.90, 0.80, 0.50, 0.95,
            0.70, 0.60, 0.85, 0.75,
            0.65, 0.90, 0.80, 0.55
        ]
    })

    # ------------------------------------------------
    # Calculate risk
    # ------------------------------------------------

    data = calculate_risk(data)

    # ------------------------------------------------
    # Rank locations
    # ------------------------------------------------

    data = rank_locations(data)

    # ------------------------------------------------
    # Select top 10
    # ------------------------------------------------

    top_10 = get_top_10(data)

    # ------------------------------------------------
    # Create output folder
    # ------------------------------------------------

    os.makedirs("../output", exist_ok=True)

    # ------------------------------------------------
    # Save result
    # ------------------------------------------------

    output_file = "../output/priority_top10.csv"

    top_10.to_csv(
        output_file,
        index=False
    )

    # ------------------------------------------------
    # Display results
    # ------------------------------------------------

    print("\n========== TOP 10 PRIORITY LOCATIONS ==========\n")

    print(
        top_10[
            [
                "rank",
                "location_id",
                "exposure",
                "vulnerability",
                "risk"
            ]
        ].to_string(index=False)
    )

    print("\nSaved to:")
    print(output_file)