import os
import math
import pandas as pd
import geopandas as gpd
import networkx as nx
from shapely.geometry import Point


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

PROJECT_DIR = os.path.dirname(BASE_DIR)

DATA_DIR = os.path.join(
    PROJECT_DIR,
    "data"
)

OUTPUT_DIR = os.path.join(
    PROJECT_DIR,
    "output"
)

SEGMENTS_FILE = os.path.join(
    DATA_DIR,
    "segments.geojson"
)

WORKER_FILE = os.path.join(
    DATA_DIR,
    "worker_profiles.csv"
)

OUTPUT_FILE = os.path.join(
    OUTPUT_DIR,
    "routing_engine_results.csv"
)


# ============================================================
# SETTINGS
# ============================================================

VULNERABILITY = {
    "rider": 1.0,
    "vendor": 1.3,
    "child": 1.5
}

# Weight used by CoolPath
SHADE_WEIGHT = 500
POLLUTION_WEIGHT = 300


# ============================================================
# LOAD SEGMENTS
# ============================================================

def load_segments():

    if not os.path.exists(SEGMENTS_FILE):
        raise FileNotFoundError(
            f"segments.geojson not found:\n{SEGMENTS_FILE}"
        )

    segments = gpd.read_file(
        SEGMENTS_FILE
    )

    print(
        f"Loaded segments: {len(segments)}"
    )

    # --------------------------------------------------------
    # Fix CRS
    # Member A segments are sometimes labelled EPSG:4326
    # even though coordinates are actually Web Mercator.
    # --------------------------------------------------------

    bounds = segments.total_bounds

    max_coordinate = max(
        abs(bounds[0]),
        abs(bounds[1]),
        abs(bounds[2]),
        abs(bounds[3])
    )

    if max_coordinate > 180:

        segments = segments.set_crs(
            "EPSG:3857",
            allow_override=True
        )

    else:

        if segments.crs is None:

            segments = segments.set_crs(
                "EPSG:4326"
            )

        segments = segments.to_crs(
            "EPSG:3857"
        )

    # --------------------------------------------------------
    # Required columns
    # --------------------------------------------------------

    if "geometry" not in segments.columns:
        raise ValueError(
            "segments.geojson has no geometry column."
        )

    # --------------------------------------------------------
    # Distance
    # --------------------------------------------------------

    segments["distance_m"] = (
        segments.geometry.length
    )

    # --------------------------------------------------------
    # Clean numeric fields
    # --------------------------------------------------------

    numeric_columns = [
        "shade_fraction",
        "pollution_score",
        "heat_index",
        "road_width",
        "speed_kmh"
    ]

    for col in numeric_columns:

        if col in segments.columns:

            segments[col] = pd.to_numeric(
                segments[col],
                errors="coerce"
            )

    # --------------------------------------------------------
    # Find shade column if Member A used another name
    # --------------------------------------------------------

    if "shade_fraction" not in segments.columns:

        possible_shade_columns = [
            "shade",
            "shade_pct",
            "shade_percent",
            "road_shade",
            "shade_fraction_"
        ]

        for col in possible_shade_columns:

            if col in segments.columns:

                segments["shade_fraction"] = pd.to_numeric(
                    segments[col],
                    errors="coerce"
                )

                break

    if "shade_fraction" not in segments.columns:

        segments["shade_fraction"] = 0.0

    # --------------------------------------------------------
    # Find pollution column
    # --------------------------------------------------------

    if "pollution_score" not in segments.columns:

        possible_pollution_columns = [
            "pollution",
            "pollution_proxy",
            "pollution_risk",
            "pollution_score_"
        ]

        for col in possible_pollution_columns:

            if col in segments.columns:

                segments["pollution_score"] = pd.to_numeric(
                    segments[col],
                    errors="coerce"
                )

                break

    if "pollution_score" not in segments.columns:

        segments["pollution_score"] = 0.0

    # --------------------------------------------------------
    # Fill missing values
    # --------------------------------------------------------

    segments["shade_fraction"] = (
        segments["shade_fraction"]
        .fillna(0)
        .clip(0, 1)
    )

    segments["pollution_score"] = (
        segments["pollution_score"]
        .fillna(0)
    )

    return segments


# ============================================================
# LOAD WORKER PROFILES
# ============================================================

def load_worker_profiles():

    if not os.path.exists(WORKER_FILE):

        raise FileNotFoundError(
            f"worker_profiles.csv not found:\n{WORKER_FILE}"
        )

    workers = pd.read_csv(
        WORKER_FILE
    )

    required = [
        "worker_type",
        "speed_kmh",
        "heat_sensitivity",
        "pollution_sensitivity"
    ]

    missing = [
        col
        for col in required
        if col not in workers.columns
    ]

    if missing:

        raise ValueError(
            f"Missing worker columns: {missing}"
        )

    print(
        "Worker profiles:",
        workers["worker_type"].tolist()
    )

    return workers


# ============================================================
# FIND NODE COLUMNS
# ============================================================

def find_node_columns(segments):

    possible_pairs = [
        ("u", "v"),
        ("from", "to"),
        ("source", "target"),
        ("start_node", "end_node"),
        ("node_u", "node_v")
    ]

    for u_col, v_col in possible_pairs:

        if (
            u_col in segments.columns
            and v_col in segments.columns
        ):

            return u_col, v_col

    return None, None


# ============================================================
# CREATE NODE IDS
# ============================================================

def create_nodes_from_geometry(segments):

    """
    If Member A data already has u/v node columns,
    those are used.

    Otherwise, nodes are generated from segment endpoints.
    """

    u_col, v_col = find_node_columns(
        segments
    )

    if u_col is not None:

        return segments, u_col, v_col

    node_lookup = {}

    next_node = 0

    u_values = []
    v_values = []

    for geom in segments.geometry:

        if geom is None or geom.is_empty:

            u_values.append(None)
            v_values.append(None)

            continue

        # ----------------------------------------------------
        # Handle LineString
        # ----------------------------------------------------

        coords = list(
            geom.coords
        )

        start = tuple(
            round(x, 3)
            for x in coords[0]
        )

        end = tuple(
            round(x, 3)
            for x in coords[-1]
        )

        if start not in node_lookup:

            node_lookup[start] = next_node
            next_node += 1

        if end not in node_lookup:

            node_lookup[end] = next_node
            next_node += 1

        u_values.append(
            node_lookup[start]
        )

        v_values.append(
            node_lookup[end]
        )

    segments["u"] = u_values
    segments["v"] = v_values

    return segments, "u", "v"


# ============================================================
# BUILD GRAPH
# ============================================================

def build_graph(
    segments,
    u_col,
    v_col,
    weight_type="distance"
):

    graph = nx.DiGraph()

    for _, row in segments.iterrows():

        u = row[u_col]
        v = row[v_col]

        if pd.isna(u) or pd.isna(v):
            continue

        u = int(u)
        v = int(v)

        distance = float(
            row["distance_m"]
        )

        shade = float(
            row["shade_fraction"]
        )

        pollution = float(
            row["pollution_score"]
        )

        # ----------------------------------------------------
        # CoolPath weight
        # ----------------------------------------------------

        if weight_type == "cool":

            weight = (
                distance
                + (1 - shade)
                * SHADE_WEIGHT
                + pollution
                * POLLUTION_WEIGHT
            )

        else:

            weight = distance

        edge_data = {
            "weight": weight,
            "distance_m": distance,
            "shade_fraction": shade,
            "pollution_score": pollution
        }

        # ----------------------------------------------------
        # IMPORTANT:
        # Never use graph[u][v] = ...
        # because NetworkX returns AtlasView.
        # ----------------------------------------------------

        graph.add_edge(
            u,
            v,
            **edge_data
        )

        # Road networks are normally bidirectional.
        graph.add_edge(
            v,
            u,
            **edge_data
        )

    return graph


# ============================================================
# SHORTEST PATH
# ============================================================

def find_shortest_path(
    graph,
    start,
    end
):

    try:

        return nx.shortest_path(
            graph,
            source=start,
            target=end,
            weight="weight"
        )

    except nx.NetworkXNoPath:

        return None

    except nx.NodeNotFound:

        return None


# ============================================================
# PATH METRICS
# ============================================================

def calculate_path_metrics(
    graph,
    path,
    worker
):

    if path is None or len(path) < 2:

        return {
            "distance_m": 0,
            "travel_time_min": 0,
            "heat_dose": 0,
            "pollution_dose": 0,
            "risk": 0
        }

    total_distance = 0
    total_heat = 0
    total_pollution = 0

    for i in range(
        len(path) - 1
    ):

        u = path[i]
        v = path[i + 1]

        edge = graph[u][v]

        distance = float(
            edge.get(
                "distance_m",
                0
            )
        )

        shade = float(
            edge.get(
                "shade_fraction",
                0
            )
        )

        pollution = float(
            edge.get(
                "pollution_score",
                0
            )
        )

        # ----------------------------------------------------
        # Heat exposure
        # ----------------------------------------------------

        heat_exposure = (
            1 - shade
        )

        # ----------------------------------------------------
        # Worker sensitivities
        # ----------------------------------------------------

        heat_dose = (
            distance
            * heat_exposure
            * float(
                worker["heat_sensitivity"]
            )
        )

        pollution_dose = (
            distance
            * pollution
            * float(
                worker["pollution_sensitivity"]
            )
        )

        total_distance += distance

        total_heat += heat_dose

        total_pollution += pollution_dose

    # --------------------------------------------------------
    # Travel time
    # --------------------------------------------------------

    speed = float(
        worker["speed_kmh"]
    )

    if speed <= 0:
        speed = 1

    travel_time_min = (
        total_distance / 1000
    ) / speed * 60

    # --------------------------------------------------------
    # Combined risk
    # --------------------------------------------------------

    vulnerability = VULNERABILITY.get(
        worker["worker_type"],
        1.0
    )

    risk = (
        (
            total_heat
            + total_pollution
        )
        / 1000
        * vulnerability
    )

    return {
        "distance_m": total_distance,
        "travel_time_min": travel_time_min,
        "heat_dose": total_heat,
        "pollution_dose": total_pollution,
        "risk": risk
    }


# ============================================================
# GET VALID NODES
# ============================================================

def get_valid_nodes(graph):

    nodes = list(
        graph.nodes
    )

    if len(nodes) < 2:

        raise ValueError(
            "Graph does not contain enough nodes."
        )

    return nodes


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n======================================")
    print("EcoTwin-X CoolPath Routing Engine")
    print("======================================\n")

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Load data
    # --------------------------------------------------------

    segments = load_segments()

    workers = load_worker_profiles()

    # --------------------------------------------------------
    # Create node IDs if required
    # --------------------------------------------------------

    segments, u_col, v_col = (
        create_nodes_from_geometry(
            segments
        )
    )

    print(
        f"Using node columns: "
        f"{u_col}, {v_col}"
    )

    # --------------------------------------------------------
    # Hours
    # --------------------------------------------------------

    hours = []

    if "hour" in segments.columns:

        hours = (
            segments["hour"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

    elif "time" in segments.columns:

        hours = (
            segments["time"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

    else:

        # Member A's standard hours
        hours = [
            "9am",
            "11am",
            "1pm",
            "3pm",
            "5pm"
        ]

    print(
        "Hours found:",
        hours
    )

    # --------------------------------------------------------
    # Build graphs
    # --------------------------------------------------------

    overall_graph = build_graph(
        segments,
        u_col,
        v_col,
        weight_type="distance"
    )

    cool_graph = build_graph(
        segments,
        u_col,
        v_col,
        weight_type="cool"
    )

    print(
        f"Graph nodes: "
        f"{overall_graph.number_of_nodes()}"
    )

    print(
        f"Graph edges: "
        f"{overall_graph.number_of_edges()}"
    )

    # --------------------------------------------------------
    # Select start/end nodes
    # --------------------------------------------------------

    nodes = get_valid_nodes(
        overall_graph
    )

    start_node = nodes[0]
    end_node = nodes[-1]

    print(
        f"Start node: {start_node}"
    )

    print(
        f"End node: {end_node}"
    )

    # --------------------------------------------------------
    # Run routing
    # --------------------------------------------------------

    results = []

    for hour in hours:

        # ----------------------------------------------------
        # If hour column exists, filter data
        # ----------------------------------------------------

        if "hour" in segments.columns:

            hour_segments = segments[
                segments["hour"].astype(str)
                == str(hour)
            ].copy()

        elif "time" in segments.columns:

            hour_segments = segments[
                segments["time"].astype(str)
                == str(hour)
            ].copy()

        else:

            hour_segments = segments.copy()

        if hour_segments.empty:

            continue

        # ----------------------------------------------------
        # Build hour-specific graphs
        # ----------------------------------------------------

        hour_overall_graph = build_graph(
            hour_segments,
            u_col,
            v_col,
            weight_type="distance"
        )

        hour_cool_graph = build_graph(
            hour_segments,
            u_col,
            v_col,
            weight_type="cool"
        )

        # ----------------------------------------------------
        # Make sure selected nodes exist
        # ----------------------------------------------------

        hour_nodes = list(
            hour_overall_graph.nodes
        )

        if (
            start_node not in hour_nodes
            or end_node not in hour_nodes
        ):

            if len(hour_nodes) < 2:
                continue

            hour_start = hour_nodes[0]
            hour_end = hour_nodes[-1]

        else:

            hour_start = start_node
            hour_end = end_node

        # ----------------------------------------------------
        # Routes
        # ----------------------------------------------------

        shortest_path = find_shortest_path(
            hour_overall_graph,
            hour_start,
            hour_end
        )

        cool_path = find_shortest_path(
            hour_cool_graph,
            hour_start,
            hour_end
        )

        # ----------------------------------------------------
        # Workers
        # ----------------------------------------------------

        for _, worker in workers.iterrows():

            worker_type = worker[
                "worker_type"
            ]

            # Shortest route metrics
            shortest_metrics = (
                calculate_path_metrics(
                    hour_overall_graph,
                    shortest_path,
                    worker
                )
            )

            # Cool route metrics
            cool_metrics = (
                calculate_path_metrics(
                    hour_cool_graph,
                    cool_path,
                    worker
                )
            )

            # ------------------------------------------------
            # Result
            # ------------------------------------------------

            results.append({

                "hour": hour,

                "worker_type":
                    worker_type,

                "shortest_distance_m":
                    shortest_metrics[
                        "distance_m"
                    ],

                "shortest_travel_time_min":
                    shortest_metrics[
                        "travel_time_min"
                    ],

                "shortest_heat_dose":
                    shortest_metrics[
                        "heat_dose"
                    ],

                "shortest_pollution_dose":
                    shortest_metrics[
                        "pollution_dose"
                    ],

                "shortest_risk":
                    shortest_metrics[
                        "risk"
                    ],

                "cool_distance_m":
                    cool_metrics[
                        "distance_m"
                    ],

                "cool_travel_time_min":
                    cool_metrics[
                        "travel_time_min"
                    ],

                "cool_heat_dose":
                    cool_metrics[
                        "heat_dose"
                    ],

                "cool_pollution_dose":
                    cool_metrics[
                        "pollution_dose"
                    ],

                "cool_risk":
                    cool_metrics[
                        "risk"
                    ],

                "risk_reduction":
                    (
                        shortest_metrics["risk"]
                        - cool_metrics["risk"]
                    ),

                "risk_reduction_percent":
                    (
                        (
                            shortest_metrics["risk"]
                            - cool_metrics["risk"]
                        )
                        / shortest_metrics["risk"]
                        * 100
                        if shortest_metrics["risk"] > 0
                        else 0
                    )
            })

    # --------------------------------------------------------
    # Save results
    # --------------------------------------------------------

    results_df = pd.DataFrame(
        results
    )

    if results_df.empty:

        print(
            "\nNo routing results were generated."
        )

        return

    results_df.to_csv(
        OUTPUT_FILE,
        index=False
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print("\n======================================")
    print("ROUTING COMPLETE")
    print("======================================")

    print(
        f"Routing records: "
        f"{len(results_df)}"
    )

    print(
        f"\nAverage shortest-route risk: "
        f"{results_df['shortest_risk'].mean():.4f}"
    )

    print(
        f"Average CoolPath risk: "
        f"{results_df['cool_risk'].mean():.4f}"
    )

    print(
        f"Average risk reduction: "
        f"{results_df['risk_reduction_percent'].mean():.2f}%"
    )

    print(
        f"\nOutput saved to:\n"
        f"{OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()