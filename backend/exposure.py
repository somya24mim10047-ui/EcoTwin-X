import geopandas as gpd


def calculate_exposure(gdf, heat_factor):
    """
    Calculate exposure for each road segment.

    Exposure = (1 - shade_frac) * heat_factor + pollution_proxy
    """

    gdf = gdf.copy()

    gdf["heat_factor"] = heat_factor

    gdf["exposure"] = (
        (1 - gdf["shade_frac"]) * gdf["heat_factor"]
        + gdf["pollution_proxy"]
    )

    return gdf


if __name__ == "__main__":

    input_file = "../data/segments.geojson"

    gdf = gpd.read_file(input_file)

    # Temporary heat factor for testing.
    # We will later replace this with the actual
    # temperature/humidity-based value.
    heat_factor = 0.80

    result = calculate_exposure(gdf, heat_factor)

    print("\nExposure calculation:\n")

    print(
        result[
            [
                "edge_id",
                "shade_frac",
                "pollution_proxy",
                "heat_factor",
                "exposure"
            ]
        ]
    )