import json
import os

hours = [9, 11, 13, 15, 17]

# Same road network for testing
roads = [
    ("E01", 101, 102, 200, 0.20, "residential", 0.10),
    ("E02", 102, 103, 200, 0.30, "primary", 0.40),
    ("E03", 101, 104, 250, 0.80, "residential", 0.05),
    ("E04", 104, 105, 250, 0.85, "residential", 0.05),
    ("E05", 105, 106, 250, 0.80, "residential", 0.05),
    ("E06", 103, 106, 250, 0.20, "primary", 0.45)
]

coordinates = {
    101: [77.5900, 12.9700],
    102: [77.5920, 12.9700],
    103: [77.5940, 12.9700],
    104: [77.5900, 12.9725],
    105: [77.5925, 12.9725],
    106: [77.5950, 12.9725]
}

features = []

for hour in hours:

    for edge_id, u, v, distance, shade, road_class, pollution in roads:

        feature = {
            "type": "Feature",
            "properties": {
                "edge_id": edge_id,
                "u": u,
                "v": v,
                "hour": hour,
                "distance_m": distance,
                "shade_frac": shade,
                "road_class": road_class,
                "pollution_proxy": pollution
            },
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    coordinates[u],
                    coordinates[v]
                ]
            }
        }

        features.append(feature)

geojson = {
    "type": "FeatureCollection",
    "features": features
}

os.makedirs("../data", exist_ok=True)

with open("../data/segments.geojson", "w") as file:
    json.dump(geojson, file, indent=4)

print("Created dummy segments.geojson")
print("Hours:", hours)
print("Total road segments:", len(features))