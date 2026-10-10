"""EcoTwin-X core: exposure-aware routing + intervention planning.

Plain functions with no UI dependencies. They are used by the Streamlit app
and exposed as tools to the Strands agent (ecotwin/agent.py).
"""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
import math

import geopandas as gpd
import networkx as nx
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "output"

HOURS = {9: "9am", 11: "11am", 13: "1pm", 15: "3pm", 17: "5pm"}  # 24h -> label
LABEL_TO_H = {v: k for k, v in HOURS.items()}
# How strongly a metre of unshaded / polluted road is penalised when choosing
# the cool route (1.0 means "an unshaded metre feels like 2 metres" for a
# worker with heat sensitivity 1.0).
HEAT_PENALTY = 1.5
POLLUTION_PENALTY = 1.0


@lru_cache(maxsize=1)
def _workers() -> pd.DataFrame:
    return pd.read_csv(DATA / "worker_profiles.csv").set_index("worker_type")


@lru_cache(maxsize=1)
def _segments() -> pd.DataFrame:
    g = gpd.read_file(DATA / "segments.geojson").set_crs(3857, allow_override=True)  # file is mislabelled 4326 but holds Web Mercator metres
    g["length_m"] = g.to_crs(32643).length  # UTM 43N (Bhopal region)
    g["hour"] = g["hour"].map(LABEL_TO_H)
    return pd.DataFrame(g.drop(columns="geometry"))


@lru_cache(maxsize=8)
def _graph(hour: int, worker: str, mode: str) -> nx.Graph:
    seg = _segments()
    seg = seg[seg["hour"] == hour]
    w = _workers().loc[worker]
    G = nx.Graph()
    for r in seg.itertuples():
        length, shade, poll = r.length_m, r.shade_frac, r.pollution_proxy
        heat = length * (1 - shade) * w.heat_sensitivity
        pol = length * poll * w.pollution_sensitivity
        weight = length if mode == "shortest" else (
            length + HEAT_PENALTY * heat + POLLUTION_PENALTY * pol)
        if G.has_edge(r.u, r.v) and G[r.u][r.v]["weight"] <= weight:
            continue
        G.add_edge(r.u, r.v, weight=weight, length=length, heat=heat, pol=pol)
    return G


def _largest_component(G: nx.Graph) -> set:
    return max(nx.connected_components(G), key=len)


@lru_cache(maxsize=1)
def default_trip() -> tuple[int, int]:
    """A reproducible, reasonably long origin/destination pair."""
    G = _graph(13, "rider", "shortest")
    nodes = sorted(_largest_component(G))
    a = nodes[0]
    dist = nx.single_source_dijkstra_path_length(G, a, weight="length")
    b = max(dist, key=dist.get)
    dist2 = nx.single_source_dijkstra_path_length(G, b, weight="length")
    a = max(dist2, key=dist2.get)
    return a, b


def _metrics(G: nx.Graph, path: list, worker: str) -> dict:
    length = heat = pol = 0.0
    for u, v in zip(path, path[1:]):
        e = G[u][v]
        length += e["length"]; heat += e["heat"]; pol += e["pol"]
    speed = float(_workers().loc[worker].speed_kmh)
    return {
        "distance_m": round(length),
        "travel_time_min": round(length / 1000 / speed * 60, 1),
        "heat_dose": round(heat),
        "pollution_dose": round(pol),
        "exposure_score": round((heat + pol) / 1000, 3),
    }


def compare_routes(worker_type: str = "rider", hour: int = 13) -> dict:
    """Shortest vs CoolPath route for one worker type and hour (24h clock:
    9, 11, 13, 15, 17). Returns distance, time, heat dose, pollution dose and
    the % exposure reduction of the cool route."""
    if worker_type not in _workers().index:
        raise ValueError(f"worker_type must be one of {list(_workers().index)}")
    if hour not in HOURS:
        raise ValueError(f"hour must be one of {list(HOURS)}")
    a, b = default_trip()
    out = {}
    for mode in ("shortest", "cool"):
        G = _graph(hour, worker_type, mode)
        path = nx.shortest_path(G, a, b, weight="weight")
        out[mode] = _metrics(G, path, worker_type)
    s, c = out["shortest"]["exposure_score"], out["cool"]["exposure_score"]
    out["exposure_reduction_pct"] = round((s - c) / s * 100, 1) if s else 0.0
    out["extra_minutes"] = round(
        out["cool"]["travel_time_min"] - out["shortest"]["travel_time_min"], 1)
    out["worker_type"], out["hour"] = worker_type, HOURS[hour]
    return out


def routing_table() -> pd.DataFrame:
    """All hours x worker types - regenerates output/routing_engine_results.csv."""
    rows = []
    for h, label in HOURS.items():
        for wt in _workers().index:
            r = compare_routes(wt, h)
            row = {"hour": label, "worker_type": wt}
            for mode in ("shortest", "cool"):
                m = r[mode]
                row.update({
                    f"{mode}_distance_m": m["distance_m"],
                    f"{mode}_travel_time_min": m["travel_time_min"],
                    f"{mode}_heat_dose": m["heat_dose"],
                    f"{mode}_pollution_dose": m["pollution_dose"],
                    f"{mode}_risk": m["exposure_score"],
                })
            row["risk_reduction"] = round(row["shortest_risk"] - row["cool_risk"], 3)
            row["risk_reduction_percent"] = r["exposure_reduction_pct"]
            rows.append(row)
    return pd.DataFrame(rows)


def intervention_options() -> list[dict]:
    """Cost and effect assumptions for each intervention (INR)."""
    return pd.read_csv(DATA / "interventions.csv").to_dict("records")


def best_plan_for_budget(budget_inr: int) -> dict:
    """Best intervention mix that fits a budget, from the precomputed
    budget-optimiser results (output/budget_optimization_results.csv)."""
    df = pd.read_csv(OUT / "budget_optimization_results.csv")
    ok = df[df["cost_inr"] <= budget_inr].sort_values(
        "total_benefit_index", ascending=False)
    if ok.empty:
        return {"error": f"No plan fits within {budget_inr} INR. "
                         f"Cheapest option costs {int(df.cost_inr.min())} INR."}
    b = ok.iloc[0]
    return {
        "strategy": b["strategy"], "cost_inr": int(b["cost_inr"]),
        "unused_budget_inr": int(budget_inr - b["cost_inr"]),
        "people_protected_index": float(b["population_protected_index"]),
        "total_benefit_index": round(float(b["total_benefit_index"]), 2),
        "note": "Planning simulation based on assumed intervention effects, "
                "not a measured prediction.",
    }


def top_priority_locations(n: int = 5) -> list[dict]:
    """Best places for a cooling stop (real OpenStreetMap places in the study
    area), ranked by worker risk, heat, pollution and accessibility."""
    df = pd.read_csv(OUT / "heat_stop_optimization.csv").sort_values("rank").head(n)
    df["name"] = df["name"].fillna("Unnamed " + df["stop_type"].astype(str))
    return df[["rank", "name", "stop_type", "nearby_road_segments",
               "mean_shade", "worker_risk", "priority_score"]].round(3).to_dict("records")


@lru_cache(maxsize=1)
def _edge_coords() -> dict:
    g = gpd.read_file(DATA / "segments.geojson").set_crs(3857, allow_override=True).to_crs(4326)
    g = g[g["hour"] == "1pm"]
    d = {}
    for r in g.itertuples():
        pts = [(y, x) for x, y in r.geometry.coords]  # (lat, lon)
        d[(r.u, r.v)] = pts
        d[(r.v, r.u)] = pts[::-1]
    return d


def route_lines(worker_type: str = "rider", hour: int = 13) -> dict:
    """Coordinates ([lat, lon] lists) of the shortest and CoolPath routes, for maps."""
    a, b = default_trip()
    ec, out = _edge_coords(), {}
    for mode in ("shortest", "cool"):
        path = nx.shortest_path(_graph(hour, worker_type, mode), a, b, weight="weight")
        line = []
        for u, v in zip(path, path[1:]):
            line.extend(ec[(u, v)])
        out[mode] = line
    return out
