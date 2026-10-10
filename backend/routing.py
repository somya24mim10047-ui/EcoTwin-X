import os
import math
import pandas as pd
import geopandas as gpd
import networkx as nx
from shapely.geometry import LineString, Point


# ============================================================
# EcoTwin-X CoolPath Routing Engine
# ============================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

SEGMENTS_FILE = os.path.join(DATA_DIR, "segments.geojson")
WORKERS_FILE = os.path.join(DATA_DIR, "worker_profiles.csv")

OUTPUT_FILE = os.path.join(
    OUTPUT_DIR,
    "routing_engine_results.csv"
)

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ============================================================
# CONFIGURATION
# ============================================================

VULNERABILITY = {
    "rider": 1.0,
    "vendor": 1.3,
    "child": 1.5
}

# These weights control CoolPath.
# Distance is still important, but environmental exposure
# has a stronger influence than before.

DISTANCE_WEIGHT = 1.0
HEAT_WEIGHT = 2500.0
POLLUTION_WEIGHT = 1500.0

# Maximum acceptable increase in route distance compared
# with the shortest route.
MAX_DISTANCE_FACTOR = 1.50


# ============================================================
# LOAD ROAD SEGMENTS
# ============================================================

print("\n======================================")
print("EcoTwin-X CoolPath Routing Engine")
print("======================================\n")

segments = gpd.read_file(SEGMENTS_FILE)

print("Loaded segments:", len(segments))


# ============================================================
# FIX CRS
# ============================================================

bounds = segments.total_bounds

if (
    abs(bounds[0]) > 180
    or abs(bounds[2]) > 180
    or abs(bounds[1]) > 90
    or abs(bounds[3]) > 90
):
    print("Detected projected road coordinates.")
    print("Correcting road CRS to EPSG:3857.")

    segments = segments.set_crs(
        "EPSG:3857",
        allow_override=True
    )

else:
    if segments.crs is None:
        segments = segments.set_crs("EPSG:4326")

    segments = segments.to_crs("EPSG:3857")


# ============================================================
# CLEAN DATA
# ============================================================

segments = segments[
    segments.geometry.notna()
].copy()

segments = segments[
    ~segments.geometry.is_empty
].copy()

segments["distance_m"] = segments.geometry.length

print("Road CRS:", segments.crs)


# ============================================================
# FIND NODE COLUMNS
# ============================================================

possible_node_pairs = [
    ("u", "v"),
    ("from", "to"),
    ("source", "target"),
    ("start_node", "end_node"),
    ("node_u", "node_v")
]

node_pair = None

for u_col, v_col in possible_node_pairs:

    if u_col in segments.columns and v_col in segments.columns:
        node_pair = (u_col, v_col)
        break


# ============================================================
# CREATE NODE IDs IF NECESSARY
# ============================================================

if node_pair is not None:

    U_COL, V_COL = node_pair

    print(
        f"Using node columns: {U_COL}, {V_COL}"
    )

else:

    print(
        "No node columns found. "
        "Creating nodes from geometry endpoints."
    )

    generated_u = []
    generated_v = []

    for geom in segments.geometry:

        if isinstance(geom, LineString):

            start = tuple(geom.coords[0])
            end = tuple(geom.coords[-1])

            generated_u.append(start)
            generated_v.append(end)

        else:

            generated_u.append(None)
            generated_v.append(None)

    segments["generated_u"] = generated_u
    segments["generated_v"] = generated_v

    U_COL = "generated_u"
    V_COL = "generated_v"

    node_pair = (U_COL, V_COL)


# ============================================================
# LOAD WORKER PROFILES
# ============================================================

workers = pd.read_csv(WORKERS_FILE)

print(
    "Worker profiles:",
    workers["worker_type"].tolist()
)


# ============================================================
# FIND AVAILABLE HOURS
# ============================================================

hour_columns = [
    "9am",
    "11am",
    "1pm",
    "3pm",
    "5pm"
]

available_hours = []

for hour in hour_columns:

    shade_col = f"shade_{hour}"
    pollution_col = f"pollution_{hour}"

    if (
        shade_col in segments.columns
        or pollution_col in segments.columns
    ):
        available_hours.append(hour)


# If explicit hour columns are not available,
# use the five project hours.

if not available_hours:
    available_hours = hour_columns


print("Hours found:", available_hours)


# ============================================================
# HELPER: FIND SHADE COLUMN
# ============================================================

def get_shade_column(hour):

    candidates = [
        f"shade_{hour}",
        f"mean_shade_{hour}",
        f"shade_fraction_{hour}",
        f"road_shade_{hour}"
    ]

    for col in candidates:

        if col in segments.columns:
            return col

    return None


# ============================================================
# HELPER: FIND POLLUTION COLUMN
# ============================================================

def get_pollution_column(hour):

    candidates = [
        f"pollution_{hour}",
        f"pollution_score_{hour}",
        "pollution"
    ]

    for col in candidates:

        if col in segments.columns:
            return col

    return None


# ============================================================
# NORMALIZE VALUES
# ============================================================

def safe_numeric(value, default=0.0):

    try:

        value = float(value)

        if math.isnan(value):
            return default

        return value

    except:

        return default


def normalize_heat(shade):

    """
    Convert shade fraction into heat exposure.

    0 shade  -> 1.0 heat exposure
    100% shade -> 0.0 heat exposure
    """

    shade = max(0.0, min(1.0, shade))

    return 1.0 - shade


def normalize_pollution(value):

    """
    Pollution values in the Member A data are already
    represented as a normalized/proxy score.

    Keep them bounded between 0 and 1.
    """

    value = safe_numeric(value)

    return max(0.0, min(1.0, value))


# ============================================================
# GRAPH BUILDER
# ============================================================

def build_graph(hour):

    graph = nx.DiGraph()

    shade_col = get_shade_column(hour)
    pollution_col = get_pollution_column(hour)

    for _, row in segments.iterrows():

        u = row[U_COL]
        v = row[V_COL]

        if pd.isna(u) or pd.isna(v):
            continue

        distance = safe_numeric(
            row["distance_m"],
            1.0
        )

        if distance <= 0:
            distance = 1.0


        # ----------------------------------------------------
        # SHADE
        # ----------------------------------------------------

        if shade_col is not None:

            shade = safe_numeric(
                row[shade_col]
            )

        else:

            shade = 0.0

        shade = max(
            0.0,
            min(1.0, shade)
        )


        # ----------------------------------------------------
        # HEAT EXPOSURE
        # ----------------------------------------------------

        heat_exposure = normalize_heat(
            shade
        )


        # ----------------------------------------------------
        # POLLUTION
        # ----------------------------------------------------

        if pollution_col is not None:

            pollution = safe_numeric(
                row[pollution_col]
            )

        else:

            pollution = 0.0

        pollution = normalize_pollution(
            pollution
        )


        # ----------------------------------------------------
        # IMPORTANT:
        #
        # CoolPath cost is now based on ENVIRONMENTAL
        # EXPOSURE rather than simply adding arbitrary
        # penalties to the distance.
        #
        # This makes the optimizer prefer cooler and cleaner
        # roads when the additional distance is reasonable.
        # ----------------------------------------------------

        environmental_penalty = (
            HEAT_WEIGHT * heat_exposure
            +
            POLLUTION_WEIGHT * pollution
        )

        cool_cost = (
            DISTANCE_WEIGHT * distance
            +
            environmental_penalty
        )


        edge_data = {

            "distance_m": distance,

            "shade": shade,

            "heat_exposure": heat_exposure,

            "pollution": pollution,

            "cool_cost": cool_cost

        }


        # Add forward edge

        graph.add_edge(
            u,
            v,
            **edge_data
        )


        # Add reverse edge

        graph.add_edge(
            v,
            u,
            **edge_data
        )


    return graph


# ============================================================
# ROUTE METRICS
# ============================================================

def calculate_route_metrics(
    graph,
    path,
    worker,
    speed_kmh
):

    total_distance = 0.0
    total_heat = 0.0
    total_pollution = 0.0

    for i in range(len(path) - 1):

        u = path[i]
        v = path[i + 1]

        edge = graph[u][v]

        distance = safe_numeric(
            edge.get("distance_m", 0)
        )

        heat = safe_numeric(
            edge.get("heat_exposure", 0)
        )

        pollution = safe_numeric(
            edge.get("pollution", 0)
        )

        total_distance += distance
        total_heat += (
            heat * distance
        )
        total_pollution += (
            pollution * distance
        )


    if total_distance <= 0:

        return {
            "distance_m": 0,
            "travel_time_min": 0,
            "heat_dose": 0,
            "pollution_dose": 0,
            "risk": 0
        }


    # --------------------------------------------------------
    # Average environmental exposure along route
    # --------------------------------------------------------

    avg_heat = (
        total_heat /
        total_distance
    )

    avg_pollution = (
        total_pollution /
        total_distance
    )


    # --------------------------------------------------------
    # Travel time
    # --------------------------------------------------------

    speed_m_per_min = (
        speed_kmh * 1000 / 60
    )

    travel_time_min = (
        total_distance /
        speed_m_per_min
    )


    # --------------------------------------------------------
    # Worker sensitivity
    # --------------------------------------------------------

    heat_sensitivity = safe_numeric(
        worker["heat_sensitivity"],
        1.0
    )

    pollution_sensitivity = safe_numeric(
        worker["pollution_sensitivity"],
        1.0
    )

    worker_type = worker["worker_type"]

    vulnerability = VULNERABILITY.get(
        worker_type,
        1.0
    )


    # --------------------------------------------------------
    # Exposure doses
    # --------------------------------------------------------

    heat_dose = (
        avg_heat
        *
        travel_time_min
        *
        heat_sensitivity
    )

    pollution_dose = (
        avg_pollution
        *
        travel_time_min
        *
        pollution_sensitivity
    )


    # --------------------------------------------------------
    # Overall risk
    # --------------------------------------------------------

    risk = (
        heat_dose
        +
        pollution_dose
    ) * vulnerability


    return {

        "distance_m": total_distance,

        "travel_time_min": travel_time_min,

        "heat_dose": heat_dose,

        "pollution_dose": pollution_dose,

        "risk": risk

    }


# ============================================================
# FIND START / END NODES
# ============================================================

all_nodes = set(
    segments[U_COL].dropna().tolist()
) | set(
    segments[V_COL].dropna().tolist()
)

all_nodes = list(all_nodes)

print("Graph nodes:", len(all_nodes))


if len(all_nodes) < 2:

    raise RuntimeError(
        "Not enough nodes to create routes."
    )


# Use deterministic endpoints.

start_node = all_nodes[0]
end_node = all_nodes[-1]

print("Start node:", start_node)
print("End node:", end_node)


# ============================================================
# MAIN ROUTING
# ============================================================

results = []


for hour in available_hours:

    print(
        f"\nProcessing hour: {hour}"
    )

    graph = build_graph(hour)

    if (
        start_node not in graph
        or end_node not in graph
    ):

        print(
            "Start/end node unavailable "
            "for this hour."
        )

        continue


    # --------------------------------------------------------
    # SHORTEST DISTANCE PATH
    # --------------------------------------------------------

    try:

        shortest_path = nx.shortest_path(
            graph,
            source=start_node,
            target=end_node,
            weight="distance_m"
        )

    except nx.NetworkXNoPath:

        print(
            "No shortest path for",
            hour
        )

        continue


    shortest_distance = 0.0

    for i in range(
        len(shortest_path) - 1
    ):

        shortest_distance += safe_numeric(
            graph[
                shortest_path[i]
            ][
                shortest_path[i + 1]
            ]["distance_m"]
        )


    # --------------------------------------------------------
    # COOL PATH
    # --------------------------------------------------------

    try:

        raw_cool_path = nx.shortest_path(
            graph,
            source=start_node,
            target=end_node,
            weight="cool_cost"
        )

    except nx.NetworkXNoPath:

        print(
            "No CoolPath for",
            hour
        )

        continue


    # --------------------------------------------------------
    # DISTANCE CONSTRAINT
    #
    # Prevent CoolPath from taking an unreasonable detour.
    #
    # It may choose a cooler/cleaner road, but only within
    # 50% of the shortest route distance.
    # --------------------------------------------------------

    cool_distance = 0.0

    for i in range(
        len(raw_cool_path) - 1
    ):

        cool_distance += safe_numeric(
            graph[
                raw_cool_path[i]
            ][
                raw_cool_path[i + 1]
            ]["distance_m"]
        )


    max_allowed_distance = (
        shortest_distance
        *
        MAX_DISTANCE_FACTOR
    )


    if cool_distance <= max_allowed_distance:

        cool_path = raw_cool_path

    else:

        # ----------------------------------------------------
        # If environmental route is too long, use a
        # distance-constrained alternative.
        #
        # Try a series of k-shortest alternatives and select
        # the lowest environmental risk among routes that
        # satisfy the distance limit.
        # ----------------------------------------------------

        selected_path = None
        selected_score = float("inf")

        try:

            candidates = nx.shortest_simple_paths(
                graph,
                start_node,
                end_node,
                weight="distance_m"
            )

            checked = 0

            for candidate in candidates:

                checked += 1

                if checked > 50:
                    break

                candidate_distance = 0.0

                for i in range(
                    len(candidate) - 1
                ):

                    candidate_distance += safe_numeric(
                        graph[
                            candidate[i]
                        ][
                            candidate[i + 1]
                        ]["distance_m"]
                    )


                if (
                    candidate_distance
                    >
                    max_allowed_distance
                ):
                    continue


                candidate_environment = 0.0

                for i in range(
                    len(candidate) - 1
                ):

                    edge = graph[
                        candidate[i]
                    ][
                        candidate[i + 1]
                    ]

                    candidate_environment += (

                        safe_numeric(
                            edge.get(
                                "heat_exposure",
                                0
                            )
                        )

                        +

                        safe_numeric(
                            edge.get(
                                "pollution",
                                0
                            )
                        )

                    )


                if (
                    candidate_environment
                    <
                    selected_score
                ):

                    selected_score = (
                        candidate_environment
                    )

                    selected_path = candidate


            if selected_path is not None:

                cool_path = selected_path

            else:

                cool_path = raw_cool_path


        except Exception:

            cool_path = raw_cool_path


    # ========================================================
    # WORKER TYPES
    # ========================================================

    for _, worker in workers.iterrows():

        worker_type = worker[
            "worker_type"
        ]

        speed_kmh = safe_numeric(
            worker["speed_kmh"],
            5.0
        )


        # ----------------------------------------------------
        # Shortest-route metrics
        # ----------------------------------------------------

        shortest_metrics = (
            calculate_route_metrics(
                graph,
                shortest_path,
                worker,
                speed_kmh
            )
        )


        # ----------------------------------------------------
        # CoolPath metrics
        # ----------------------------------------------------

        cool_metrics = (
            calculate_route_metrics(
                graph,
                cool_path,
                worker,
                speed_kmh
            )
        )


        # ----------------------------------------------------
        # Risk reduction
        # ----------------------------------------------------

        shortest_risk = (
            shortest_metrics["risk"]
        )

        cool_risk = (
            cool_metrics["risk"]
        )


        if shortest_risk > 0:

            risk_reduction = (
                (
                    shortest_risk
                    -
                    cool_risk
                )
                /
                shortest_risk
            ) * 100

        else:

            risk_reduction = 0.0


        results.append({

            "hour": hour,

            "worker_type": worker_type,

            "shortest_distance_m":
                shortest_metrics[
                    "distance_m"
                ],

            "coolpath_distance_m":
                cool_metrics[
                    "distance_m"
                ],

            "shortest_travel_time_min":
                shortest_metrics[
                    "travel_time_min"
                ],

            "coolpath_travel_time_min":
                cool_metrics[
                    "travel_time_min"
                ],

            "shortest_heat_dose":
                shortest_metrics[
                    "heat_dose"
                ],

            "coolpath_heat_dose":
                cool_metrics[
                    "heat_dose"
                ],

            "shortest_pollution_dose":
                shortest_metrics[
                    "pollution_dose"
                ],

            "coolpath_pollution_dose":
                cool_metrics[
                    "pollution_dose"
                ],

            "shortest_risk":
                shortest_risk,

            "coolpath_risk":
                cool_risk,

            "risk_reduction_percent":
                risk_reduction

        })


# ============================================================
# SAVE RESULTS
# ============================================================

results_df = pd.DataFrame(
    results
)


print("\n======================================")
print("ROUTING COMPLETE")
print("======================================")

print(
    "Routing records:",
    len(results_df)
)


if len(results_df) > 0:

    avg_shortest = results_df[
        "shortest_risk"
    ].mean()

    avg_cool = results_df[
        "coolpath_risk"
    ].mean()

    avg_reduction = results_df[
        "risk_reduction_percent"
    ].mean()


    print(
        f"\nAverage shortest-route risk: "
        f"{avg_shortest:.4f}"
    )

    print(
        f"Average CoolPath risk: "
        f"{avg_cool:.4f}"
    )

    print(
        f"Average risk reduction: "
        f"{avg_reduction:.2f}%"
    )


results_df.to_csv(
    OUTPUT_FILE,
    index=False
)


print("\nOutput saved to:")
print(OUTPUT_FILE)

print("\n======================================")