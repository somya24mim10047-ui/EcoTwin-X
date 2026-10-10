import streamlit as st
import geopandas as gpd
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ecotwin import core, agent as eco_agent


# ============================================================
# PROJECT PATHS
# ============================================================

# Resolve the project root safely for both local and Streamlit deployment.
# If app.py is at the repository root, data/output are next to it.
# If app.py is inside frontend/, data/output are one level above.
APP_DIR = Path(__file__).resolve().parent
if (APP_DIR / "data").exists() and (APP_DIR / "output").exists():
    PROJECT_DIR = APP_DIR
elif (APP_DIR.parent / "data").exists() and (APP_DIR.parent / "output").exists():
    PROJECT_DIR = APP_DIR.parent
else:
    # Default to the directory containing the running app.
    PROJECT_DIR = APP_DIR

DATA_DIR = PROJECT_DIR / "data"
OUTPUT_DIR = PROJECT_DIR / "output"


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="EcoTwin-X",
    page_icon="🌿",
    layout="wide"
)


# ============================================================
# TITLE
# ============================================================

st.title("🌿 EcoTwin-X")

st.caption(
    "HeatStop & CoolPath Environmental Intervention Twin"
)

st.markdown(
    """
    **Simulating environmental interventions before they are built
    to reduce heat and pollution exposure for vulnerable urban populations.**
    """
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("EcoTwin-X")

page = st.sidebar.radio(
    "Navigate",
    [
        "Overview",
        "Heat & Pollution",
        "Equity & Exposure",
        "CoolPath",
        "AI Planner (Strands Agent)",
        "HeatStop Planner",
        "Intervention Twin",
        "Intervention Optimizer",
        "Environmental Time Machine",
        "Validation"
    ]
)


# ============================================================
# HELPER FUNCTION — LOAD CSV
# ============================================================

def load_csv(filename):
    """Safely load a CSV file from the output folder."""

    path = OUTPUT_DIR / filename

    if not path.exists():
        st.warning(f"File not found: {path}")
        return None

    try:
        return pd.read_csv(path)

    except pd.errors.EmptyDataError:
        st.info(
            f"{filename} is empty. No data is available for this section."
        )
        return None

    except Exception as e:
        st.error(f"Could not load {filename}: {e}")
        return None


# ============================================================
# HELPER FUNCTION — LOAD GEOJSON
# ============================================================

def load_geojson(filename):
    """Safely load a GeoJSON file from the data folder."""

    path = DATA_DIR / filename

    if not path.exists():
        st.warning(f"File not found: {path}")
        return None

    try:
        return gpd.read_file(path)

    except Exception as e:
        st.error(f"Could not load {filename}: {e}")
        return None


# ============================================================
# HELPER FUNCTION — DISPLAY GEOJSON MAP
# ============================================================

def show_geo_map(gdf, title="Map"):
    """
    Display actual GeoJSON geometries using Folium.

    Converts projected CRS such as EPSG:3857 to EPSG:4326
    and cleans NumPy values before converting to GeoJSON.
    """

    if gdf is None or gdf.empty:
        st.info("No geographic data available.")
        return

    try:
        # ----------------------------------------------------
        # COPY DATA
        # ----------------------------------------------------

        map_gdf = gdf.copy()

        # ----------------------------------------------------
        # CONVERT CRS
        # ----------------------------------------------------

        if map_gdf.crs is not None:
            map_gdf = map_gdf.to_crs(epsg=4326)

        # ----------------------------------------------------
        # KEEP ONLY USEFUL DISPLAY COLUMNS
        # ----------------------------------------------------

        useful_columns = []

        for column in [
            "shade_frac",
            "pollution_proxy",
            "highway",
            "road_type",
            "name"
        ]:
            if column in map_gdf.columns:
                useful_columns.append(column)

        # Keep geometry + useful attributes only
        if useful_columns:
            map_gdf = map_gdf[
                useful_columns + ["geometry"]
            ]
        else:
            map_gdf = map_gdf[
                ["geometry"]
            ]

        # ----------------------------------------------------
        # CONVERT PROPERTIES TO SAFE JSON VALUES
        # ----------------------------------------------------

        import numpy as np

        def clean_value(value):

            if isinstance(value, np.ndarray):
                return value.tolist()

            if isinstance(value, np.generic):
                return value.item()

            if pd.isna(value):
                return None

            return value

        for column in map_gdf.columns:

            if column != "geometry":

                map_gdf[column] = map_gdf[column].apply(
                    clean_value
                )

        # ----------------------------------------------------
        # REMOVE INVALID GEOMETRIES
        # ----------------------------------------------------

        map_gdf = map_gdf[
            map_gdf.geometry.notna()
        ].copy()

        # ----------------------------------------------------
        # CALCULATE CENTER
        # ----------------------------------------------------

        center_point = (
            map_gdf.geometry
            .union_all()
            .centroid
        )

        center_lat = center_point.y
        center_lon = center_point.x

        # ----------------------------------------------------
        # CREATE MAP
        # ----------------------------------------------------

        m = folium.Map(
            location=[
                center_lat,
                center_lon
            ],
            zoom_start=15,
            tiles="OpenStreetMap"
        )

        # ----------------------------------------------------
        # TOOLTIP
        # ----------------------------------------------------

        tooltip_fields = []
        tooltip_aliases = []

        if "shade_frac" in map_gdf.columns:

            tooltip_fields.append(
                "shade_frac"
            )

            tooltip_aliases.append(
                "Shade Fraction:"
            )

        if "pollution_proxy" in map_gdf.columns:

            tooltip_fields.append(
                "pollution_proxy"
            )

            tooltip_aliases.append(
                "Pollution Proxy:"
            )

        if "highway" in map_gdf.columns:

            tooltip_fields.append(
                "highway"
            )

            tooltip_aliases.append(
                "Road Type:"
            )

        # ----------------------------------------------------
        # ROAD STYLE
        # ----------------------------------------------------

        def style_function(feature):

            return {
                "color": "#2E86DE",
                "weight": 3,
                "opacity": 0.8
            }

        # ----------------------------------------------------
        # ADD GEOJSON
        # ----------------------------------------------------

        geojson_kwargs = {
            "data": map_gdf.to_json(),
            "name": title,
            "style_function": style_function
        }

        if tooltip_fields:

            geojson_kwargs["tooltip"] = (
                folium.GeoJsonTooltip(
                    fields=tooltip_fields,
                    aliases=tooltip_aliases,
                    localize=True,
                    sticky=False
                )
            )

        folium.GeoJson(
            **geojson_kwargs
        ).add_to(m)

        # ----------------------------------------------------
        # LAYER CONTROL
        # ----------------------------------------------------

        folium.LayerControl().add_to(m)

        # ----------------------------------------------------
        # DISPLAY
        # ----------------------------------------------------

        st.subheader(title)

        st_folium(
            m,
            width=None,
            height=550,
            returned_objects=[]
        )

    except Exception as e:

        st.error(
            f"Could not display map: {e}"
        )

# ============================================================
# PAGE 1 — OVERVIEW
# ============================================================

if page == "Overview":

    st.header("🌿 EcoTwin-X Overview")

    st.markdown(
        """
        EcoTwin-X is an environmental digital twin designed to understand
        how urban interventions can reduce heat and pollution exposure.

        The system combines:

        - 🌡️ Street-level heat analysis
        - 🌫️ Pollution exposure analysis
        - 👥 Vulnerability and equity analysis
        - 🛣️ CoolPath route optimization
        - 🧊 HeatStop planning
        - 🌳 Tree and green-corridor interventions
        - 🔮 Future impact simulation
        - 🎯 Budget-aware intervention optimization
        - ⏳ Environmental Time Machine
        """
    )

    st.success(
        "**New here? Start in 3 steps:** 1) open **CoolPath** and pick a worker and "
        "time of day  2) open **AI Planner** and ask a question in plain English  "
        "3) open **Intervention Optimizer** to see what a budget can buy."
    )

    st.divider()

    st.subheader("What the model finds (computed from the data)")

    _rt = load_csv("routing_engine_results.csv")
    _seg_n = 3106
    col1, col2, col3, col4 = st.columns(4)
    if _rt is not None and not _rt.empty:
        col1.metric("Best exposure cut (CoolPath)", f"{_rt.risk_reduction_percent.max():.0f}%",
                    help="Largest reduction in heat + pollution dose vs the shortest route")
        col2.metric("Average exposure cut", f"{_rt.risk_reduction_percent.mean():.0f}%")
        _extra = (_rt.cool_travel_time_min - _rt.shortest_travel_time_min)
        col3.metric("Typical extra travel time", f"{_extra[_rt.worker_type=='rider'].mean():.1f} min",
                    help="Cycling/riding trip, CoolPath vs shortest")
    col4.metric("Road segments modelled", f"{_seg_n:,}")

    st.caption(
        "Study area: central Bhopal, India (OpenStreetMap roads and buildings, "
        "sun-angle shadow model). Intervention costs and effects are assumptions, "
        "so results are planning simulations, not measurements."
    )

    st.divider()

    st.subheader("System Flow")

    st.markdown(
        """
        **Environmental Data → Exposure Model → Equity Analysis
        → CoolPath → HeatStop → Intervention Twin → Future Impact**
        """
    )

    st.info(
        "EcoTwin-X helps planners test environmental interventions "
        "before physically implementing them."
    )


# ============================================================
# PAGE 2 — HEAT & POLLUTION
# ============================================================

elif page == "Heat & Pollution":

    st.header("🌡️ Heat & Pollution Layer")

    st.markdown(
        """
        This page shows the environmental conditions of the road network.

        **Heat layer:** based on road shade availability.

        **Pollution layer:** based on road hierarchy and pollution proxy values.
        """
    )

    # --------------------------------------------------------
    # HEAT / SHADE
    # --------------------------------------------------------

    st.subheader("🌤️ Street Heat & Shade")

    shade_files = {

        "9 AM":
            "roads_with_shade_9am.geojson",

        "11 AM":
            "roads_with_shade_11am.geojson",

        "1 PM":
            "roads_with_shade_1pm.geojson",

        "3 PM":
            "roads_with_shade_3pm.geojson",

        "5 PM":
            "roads_with_shade_5pm.geojson"
    }

    selected_time = st.selectbox(
        "Select Time",
        list(shade_files.keys())
    )

    shade_gdf = load_geojson(
        shade_files[selected_time]
    )

    if shade_gdf is not None:

        st.success(
            f"{len(shade_gdf):,} road segments available for {selected_time}."
        )

        show_geo_map(
            shade_gdf,
            f"Shade / Heat Map — {selected_time}"
        )

        # ----------------------------------------------------
        # NUMERIC DATA SUMMARY
        # ----------------------------------------------------

        numeric_columns = shade_gdf.select_dtypes(
            include="number"
        ).columns.tolist()

        if numeric_columns:

            st.subheader("Environmental Data Summary")

            selected_column = st.selectbox(
                "View numeric environmental variable",
                numeric_columns
            )

            st.dataframe(
                shade_gdf[
                    [selected_column]
                ].describe().round(3),
                use_container_width=True
            )

    # --------------------------------------------------------
    # POLLUTION
    # --------------------------------------------------------

    st.divider()

    st.subheader("🌫️ Pollution Layer")

    pollution_gdf = load_geojson(
        "roads_with_pollution.geojson"
    )

    if pollution_gdf is not None:

        st.success(
            f"{len(pollution_gdf):,} pollution road segments available."
        )

        show_geo_map(
            pollution_gdf,
            "Road Pollution Proxy Map"
        )

        if "pollution_proxy" in pollution_gdf.columns:

            st.subheader(
                "Pollution Proxy Distribution"
            )

            fig = px.histogram(
                pollution_gdf,
                x="pollution_proxy",
                nbins=20,
                title="Pollution Proxy Distribution"
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )


# ============================================================
# PAGE 3 — EQUITY & EXPOSURE
# ============================================================

elif page == "Equity & Exposure":

    st.header("⚖️ Equity & Exposure")

    st.markdown(
        """
        This module identifies locations where **environmental exposure
        and vulnerability combine to create higher priority risks**.
        """
    )

    # --------------------------------------------------------
    # BASELINE SUMMARY
    # --------------------------------------------------------

    baseline = load_csv(
        "baseline_summary.csv"
    )

    if baseline is not None and not baseline.empty:

        st.subheader(
            "📊 Baseline Environmental Exposure"
        )

        col1, col2, col3, col4 = st.columns(4)

        with col1:

            st.metric(
                "Average Exposure",
                f"{baseline['average_exposure'].mean():.3f}"
            )

        with col2:

            st.metric(
                "Maximum Exposure",
                f"{baseline['maximum_exposure'].max():.3f}"
            )

        with col3:

            st.metric(
                "Average Shade",
                f"{baseline['average_shade'].mean():.3f}"
            )

        with col4:

            st.metric(
                "Average Pollution",
                f"{baseline['average_pollution'].mean():.3f}"
            )

        # ----------------------------------------------------
        # EXPOSURE BY HOUR
        # ----------------------------------------------------

        st.subheader(
            "Exposure Across the Day"
        )

        fig_exposure = px.line(
            baseline,
            x="hour",
            y="average_exposure",
            markers=True,
            title="Average Road-Network Exposure by Hour"
        )

        fig_exposure.update_layout(
            xaxis_title="Hour",
            yaxis_title="Average Exposure"
        )

        st.plotly_chart(
            fig_exposure,
            use_container_width=True
        )

        # ----------------------------------------------------
        # SHADE + POLLUTION
        # ----------------------------------------------------

        col1, col2 = st.columns(2)

        with col1:

            fig_shade = px.line(
                baseline,
                x="hour",
                y="average_shade",
                markers=True,
                title="Average Shade"
            )

            st.plotly_chart(
                fig_shade,
                use_container_width=True
            )

        with col2:

            fig_pollution = px.line(
                baseline,
                x="hour",
                y="average_pollution",
                markers=True,
                title="Average Pollution Proxy"
            )

            st.plotly_chart(
                fig_pollution,
                use_container_width=True
            )

        # ----------------------------------------------------
        # BASELINE TABLE
        # ----------------------------------------------------

        st.subheader(
            "Baseline Summary"
        )

        st.dataframe(
            baseline,
            use_container_width=True
        )

    # --------------------------------------------------------
    # PRIORITY LOCATIONS
    # --------------------------------------------------------

    st.divider()

    st.subheader(
        "🚨 Top 10 Environmental Priority Locations"
    )

    priority = load_csv(
        "priority_top10.csv"
    )

    if priority is not None and not priority.empty:

        top_location = priority.iloc[0]

        # ----------------------------------------------------
        # TOP LOCATION METRICS
        # ----------------------------------------------------

        col1, col2, col3, col4 = st.columns(4)

        with col1:

            st.metric(
                "Highest-Risk Location",
                top_location["location_id"]
            )

        with col2:

            st.metric(
                "Highest Risk",
                f"{top_location['risk']:.3f}"
            )

        with col3:

            st.metric(
                "Exposure",
                f"{top_location['exposure']:.2f}"
            )

        with col4:

            st.metric(
                "Vulnerability",
                f"{top_location['vulnerability']:.2f}"
            )

        st.info(
            "Priority Risk = Exposure × Vulnerability. "
            "Locations with both high environmental exposure and "
            "high vulnerability receive higher priority."
        )

        # ----------------------------------------------------
        # RISK RANKING
        # ----------------------------------------------------

        st.subheader(
            "Risk Ranking"
        )

        risk_chart = px.bar(
            priority.sort_values(
                "risk",
                ascending=True
            ),
            x="risk",
            y="location_id",
            orientation="h",
            text="risk",
            title="Top 10 Locations by Environmental Risk"
        )

        risk_chart.update_traces(
            texttemplate="%{text:.3f}",
            textposition="outside"
        )

        risk_chart.update_layout(
            xaxis_title="Risk Score",
            yaxis_title="Location"
        )

        st.plotly_chart(
            risk_chart,
            use_container_width=True
        )

        # ----------------------------------------------------
        # EXPOSURE VS VULNERABILITY
        # ----------------------------------------------------

        st.subheader(
            "Exposure vs Vulnerability"
        )

        scatter = px.scatter(
            priority,
            x="exposure",
            y="vulnerability",
            size="risk",
            color="risk",
            hover_name="location_id",
            text="location_id",
            title="Environmental Exposure vs Vulnerability"
        )

        scatter.update_layout(
            xaxis_title="Exposure",
            yaxis_title="Vulnerability"
        )

        st.plotly_chart(
            scatter,
            use_container_width=True
        )

        # ----------------------------------------------------
        # PRIORITY TABLE
        # ----------------------------------------------------

        st.subheader(
            "Priority Location Table"
        )

        display_priority = priority[
            [
                "rank",
                "location_id",
                "latitude",
                "longitude",
                "exposure",
                "vulnerability",
                "risk"
            ]
        ].copy()

        display_priority[
            [
                "exposure",
                "vulnerability",
                "risk"
            ]
        ] = display_priority[
            [
                "exposure",
                "vulnerability",
                "risk"
            ]
        ].round(3)

        st.dataframe(
            display_priority,
            use_container_width=True,
            hide_index=True
        )

        # ----------------------------------------------------
        # PRIORITY MAP
        # ----------------------------------------------------

        st.subheader(
            "📍 Priority Risk Map"
        )

        map_data = priority[
            [
                "latitude",
                "longitude"
            ]
        ].copy()

        map_data["risk"] = priority["risk"]

        st.map(
            map_data[
                [
                    "latitude",
                    "longitude"
                ]
            ]
        )

        # ----------------------------------------------------
        # RISK MODEL
        # ----------------------------------------------------

        st.subheader(
            "Risk Model"
        )

        st.markdown(
            """
            ### Worker Exposure Risk

            **Risk Score = 0.7 × Heat Dose + 0.3 × Pollution Dose**

            The worker exposure model is designed for three worker groups:

            - 🛵 **Rider**
            - 🏪 **Vendor**
            - 👶 **Child**

            A higher heat dose or pollution dose increases the worker's
            environmental exposure risk.
            """
        )

    else:

        st.warning(
            "priority_top10.csv is not available."
        )


# ============================================================
# PAGE 4 — COOLPATH
# ============================================================

elif page == "CoolPath":

    st.header("🛣️ CoolPath Route Finder")

    st.markdown(
        """
        The shortest road is often the hottest and most polluted. **CoolPath** picks
        a route with more shade and cleaner air, and shows exactly what you gain
        and what it costs in extra time.
        """
    )

    c1, c2 = st.columns(2)
    worker = c1.selectbox("Who is travelling?", ["rider", "vendor", "child"])
    hour = c2.select_slider(
        "Time of day", options=list(core.HOURS.keys()),
        value=15, format_func=lambda h: core.HOURS[h])

    with st.spinner("Finding routes..."):
        res = core.compare_routes(worker, hour)
        lines = core.route_lines(worker, hour)

    m1, m2, m3 = st.columns(3)
    m1.metric("Heat + pollution exposure", f"-{res['exposure_reduction_pct']}%",
              help="CoolPath vs shortest route")
    m2.metric("Extra travel time", f"+{res['extra_minutes']} min")
    m3.metric("Distance", f"{res['cool']['distance_m']} m",
              f"+{res['cool']['distance_m'] - res['shortest']['distance_m']} m vs shortest",
              delta_color="off")

    fmap = folium.Map(location=lines["shortest"][0], zoom_start=14, tiles="https://tile.openstreetmap.org/{z}/{x}/{y}.png", attr="© OpenStreetMap contributors")
    folium.PolyLine(lines["shortest"], color="#d62728", weight=5,
                    tooltip="Shortest route").add_to(fmap)
    folium.PolyLine(lines["cool"], color="#2ca02c", weight=5,
                    tooltip="CoolPath route").add_to(fmap)
    _pts = lines["shortest"] + lines["cool"]
    fmap.fit_bounds([[min(p[0] for p in _pts), min(p[1] for p in _pts)],
                     [max(p[0] for p in _pts), max(p[1] for p in _pts)]])
    st_folium(fmap, height=450, use_container_width=True, returned_objects=[])
    st.caption("🔴 Shortest route   🟢 CoolPath route (more shade, cleaner air)")

    routing = load_csv("routing_engine_results.csv")
    if routing is not None and not routing.empty:
        st.subheader("Exposure reduction across the day")
        fig = px.bar(
            routing, x="hour", y="risk_reduction_percent", color="worker_type",
            barmode="group",
            labels={"risk_reduction_percent": "Exposure reduction (%)",
                    "hour": "Time of day", "worker_type": "Worker"})
        st.plotly_chart(fig, use_container_width=True)
        with st.expander("See the full table"):
            st.dataframe(routing, use_container_width=True)


# ============================================================
# AI PLANNER — STRANDS AGENT
# ============================================================

elif page == "AI Planner (Strands Agent)":

    st.header("🤖 AI Planner")
    st.markdown(
        """
        Ask in plain English. The agent is built with the **AWS open-source
        Strands Agents SDK** and answers by calling EcoTwin-X's own analysis as
        tools (CoolPath routing, cooling-stop ranking, budget planning). It
        never makes up numbers.
        """
    )

    examples = [
        "Is the cool route worth it for a vendor at 5pm?",
        "Where should we build cooling stops?",
        "We have a budget of 10 lakh, what should we build?",
    ]
    cols = st.columns(len(examples))
    for col, ex in zip(cols, examples):
        if col.button(ex, use_container_width=True):
            st.session_state["q"] = ex

    question = st.text_input("Your question", key="q")

    if question:
        with st.spinner("Thinking..."):
            answer, mode = eco_agent.ask(question)
        st.markdown(answer)
        if mode == "strands-agent":
            st.caption("Answered by the Strands agent using EcoTwin-X tools.")
        else:
            st.caption(
                "Offline mode: no language model is configured, so the same "
                "EcoTwin-X tools were called with simple rules. Set ECOTWIN_MODEL "
                "(bedrock or ollama) to turn on the full Strands agent."
            )


# ============================================================
# PAGE 5 — HEATSTOP PLANNER
# ============================================================

elif page == "HeatStop Planner":

    st.header(
        "🧊 HeatStop Planner"
    )

    st.markdown(
        """
        The HeatStop Planner identifies locations where cooling
        infrastructure can provide environmental benefits.
        """
    )

    # --------------------------------------------------------
    # SELECTED STOPS
    # --------------------------------------------------------

    selected_stops = load_csv(
        "selected_heat_stops.csv"
    )

    if selected_stops is not None and not selected_stops.empty:

        st.subheader(
            "Selected Heat Stops"
        )

        st.dataframe(
            selected_stops,
            use_container_width=True
        )

    # --------------------------------------------------------
    # CANDIDATE STOPS
    # --------------------------------------------------------

    candidate_stops = load_geojson(
        "candidate_stops_clean.geojson"
    )

    if candidate_stops is not None:

        st.subheader(
            "Candidate Heat Stop Locations"
        )

        st.success(
            f"{len(candidate_stops):,} candidate locations available."
        )

        show_geo_map(
            candidate_stops,
            "Candidate Heat Stops"
        )


# ============================================================
# PAGE 6 — INTERVENTION TWIN
# ============================================================

elif page == "Intervention Twin":

    st.header(
        "🔮 Environmental Intervention Twin"
    )

    st.markdown(
        """
        This module simulates what could happen if environmental
        interventions are implemented.

        Available intervention types include:

        - 🧊 Cooling Stops
        - 🌳 Tree Plantation
        - 🌿 Green Corridors
        """
    )

    impact = load_csv(
        "intervention_impact_summary.csv"
    )

    comparison = load_csv(
        "comparison_metrics.csv"
    )

    # --------------------------------------------------------
    # INTERVENTION IMPACT
    # --------------------------------------------------------

    if impact is not None and not impact.empty:

        st.subheader(
            "Intervention Impact"
        )

        st.dataframe(
            impact,
            use_container_width=True
        )

    # --------------------------------------------------------
    # COMPARISON
    # --------------------------------------------------------

    if comparison is not None and not comparison.empty:

        st.subheader(
            "Before vs Future Comparison"
        )

        st.dataframe(
            comparison,
            use_container_width=True
        )

        numeric_columns = comparison.select_dtypes(
            include="number"
        ).columns.tolist()

        if numeric_columns:

            selected_metric = st.selectbox(
                "Select comparison metric",
                numeric_columns
            )

            fig = px.bar(
                comparison,
                y=selected_metric,
                title=f"Intervention Comparison — {selected_metric}"
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )


        # --------------------------------------------------------
        # ENVIRONMENTAL DOMINO IMPACT
        # --------------------------------------------------------

        st.divider()
        st.subheader("🔗 Environmental Domino Impact")
        st.markdown("See how one intervention can create a chain of environmental and human benefits.")

        domino_choice = st.selectbox(
            "Choose intervention for the impact chain",
            ["100 Trees", "3 Cooling Stops", "1 Green Corridor"],
            key="domino_choice"
        )

        if domino_choice == "100 Trees":
            chain = [("100 Trees", "Heat Exposure ↓ 10%"), ("Heat Exposure", "Worker Heat Stress ↓ 8%"), ("Worker Heat Stress", "Energy Demand ↓ 3%"), ("Energy Demand", "Pollution Exposure ↓ 3%"), ("Pollution Exposure", "Population Protected ↑ 275") ]
        elif domino_choice == "3 Cooling Stops":
            chain = [("3 Cooling Stops", "Heat Exposure ↓ 15%"), ("Heat Exposure", "Worker Heat Stress ↓ 12%"), ("Worker Heat Stress", "Energy Demand ↓ 4%"), ("Energy Demand", "Pollution Exposure ↓ 5%"), ("Pollution Exposure", "Population Protected ↑ 2,750") ]
        else:
            chain = [("1 Green Corridor", "Heat Exposure ↓ 20%"), ("Heat Exposure", "Worker Heat Stress ↓ 16%"), ("Worker Heat Stress", "Energy Demand ↓ 6%"), ("Energy Demand", "Pollution Exposure ↓ 8%"), ("Pollution Exposure", "Population Protected ↑ 4,000") ]

        flow = '<div class="info-box">' + "<br><br>↓<br><br>".join([f"<b>{a}</b> → {b}" for a,b in chain]) + "</div>"
        st.markdown(flow, unsafe_allow_html=True)
        st.caption("Domino Impact is a scenario model for demonstrating cascading benefits; it is not a direct measurement of electricity or AQI change.")



# ============================================================
# PAGE 7 — INTERVENTION OPTIMIZER
# ============================================================

elif page == "Intervention Optimizer":

    st.header(
        "🎯 Intervention Optimizer"
    )

    st.markdown(
        """
        The Intervention Optimizer compares intervention strategies using environmental benefit, cost and available budget.
        """
    )

    negotiator = load_csv(
        "environmental_negotiator_result.csv"
    )

    budget = load_csv(
        "budget_optimization_results.csv"
    )

    # --------------------------------------------------------
    # OPTIMIZER
    # --------------------------------------------------------

    if negotiator is not None and not negotiator.empty:

        st.subheader(
            "Recommended Intervention Strategy"
        )

        st.dataframe(
            negotiator,
            use_container_width=True
        )

    # --------------------------------------------------------
    # BUDGET
    # --------------------------------------------------------

    if budget is not None and not budget.empty:

        st.subheader(
            "Budget Optimization"
        )

        st.dataframe(
            budget,
            use_container_width=True
        )

        numeric_columns = budget.select_dtypes(
            include="number"
        ).columns.tolist()

        if numeric_columns:

            selected_metric = st.selectbox(
                "Select budget metric",
                numeric_columns
            )

            fig = px.bar(
                budget,
                y=selected_metric,
                title=f"Budget Optimization — {selected_metric}"
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )


# ============================================================
# PAGE 8 — ENVIRONMENTAL TIME MACHINE
# ============================================================

elif page == "Environmental Time Machine":

    st.header("⏳ Environmental Time Machine")

    st.markdown("""
        Travel from the **past → present → future** and compare what
        happens when environmental interventions are introduced.
        """)

    st.info("The historical and future values below are normalized scenario indices for the demo. They show the Time Machine concept; they are not claimed historical measurements.")

    timeline = pd.DataFrame({
        "Year": [2018, 2025, 2030, 2030],
        "Scenario": ["Past", "Present", "Future — No Intervention", "Future — With Intervention"],
        "Tree Cover (%)": [42, 28, 22, 38],
        "Built-up (%)": [35, 51, 60, 60],
        "Heat Risk": [58, 82, 94, 63]
    })

    st.subheader("🕰️ Past → Present → Future")
    st.dataframe(timeline, use_container_width=True, hide_index=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("2018 Heat Risk", "58")
    with c2: st.metric("2025 Heat Risk", "82", "+24")
    with c3: st.metric("2030 Without Action", "94", "+12")
    with c4: st.metric("2030 With Action", "63", "−31")

    st.subheader("📈 Heat Risk Through Time")
    chart_data = pd.DataFrame({
        "Year": [2018, 2025, 2030, 2030],
        "Heat Risk": [58, 82, 94, 63],
        "Scenario": ["Past", "Present", "Future — No Intervention", "Future — With Intervention"]
    })
    fig = px.line(chart_data, x="Year", y="Heat Risk", color="Scenario", markers=True, text="Heat Risk", title="Environmental Risk Trajectory")
    fig.update_layout(xaxis_title="Year", yaxis_title="Normalized Heat Risk (0–100)", yaxis_range=[0, 100])
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("🌳 Test Your Future Intervention")
    trees = st.slider("Additional Trees", 0, 2000, 1000, 100)
    cool_roofs = st.slider("Cool Roofs", 0, 500, 150, 25)
    estimated_reduction = min(31, (trees / 1000) * 20 + (cool_roofs / 150) * 11)
    projected_risk = max(20, 94 - estimated_reduction)

    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Trees Added", f"{trees:,}")
    with c2: st.metric("Cool Roofs", f"{cool_roofs:,}")
    with c3: st.metric("Projected 2030 Heat Risk", f"{projected_risk:.0f}")

    st.success(f"With this intervention scenario, projected 2030 heat risk falls from 94 to approximately {projected_risk:.0f}.")
    st.caption("Projection uses a simple scenario-response model for the hackathon demo. Replace with calibrated historical/forecast data when available.")


# ============================================================
# PAGE 9 — VALIDATION
# ============================================================

elif page == "Validation":

    st.header(
        "✅ Model Validation"
    )

    st.markdown(
        """
        These are consistency checks (not comparisons with measured field data). They check whether the environmental
        heat, exposure, routing, and intervention models behave consistently.
        """
    )

    # --------------------------------------------------------
    # VALIDATION RESULTS
    # --------------------------------------------------------

    validation = load_csv(
        "validation_results.csv"
    )

    if validation is not None and not validation.empty:

        st.subheader(
            "Validation Results"
        )

        st.dataframe(
            validation,
            use_container_width=True,
            hide_index=True
        )

        # ----------------------------------------------------
        # VALIDATION ACCURACY
        # ----------------------------------------------------

        if "match" in validation.columns:

            accuracy = validation["match"].mean() * 100

            st.metric(
                "Validation Accuracy",
                f"{accuracy:.1f}%"
            )

            st.subheader(
                "Validation Summary"
            )

            if accuracy == 100:

                st.success(
                    "All validation cases matched the expected results."
                )

            else:

                st.warning(
                    f"{accuracy:.1f}% of validation cases matched."
                )

    else:

        st.warning(
            "validation_results.csv is not available or is empty."
        )

    # --------------------------------------------------------
    # VALIDATION REPORT
    # --------------------------------------------------------

    st.divider()

    validation_report = load_csv(
        "validation_report.csv"
    )

    if validation_report is not None and not validation_report.empty:

        st.subheader(
            "Validation Report"
        )

        st.dataframe(
            validation_report,
            use_container_width=True,
            hide_index=True
        )

    # --------------------------------------------------------
    # INTERVENTION VALIDATION
    # --------------------------------------------------------

    intervention_validation_path = (
        OUTPUT_DIR / "intervention_validation.csv"
    )

    if intervention_validation_path.exists():

        try:

            intervention_validation = pd.read_csv(
                intervention_validation_path
            )

            if not intervention_validation.empty:

                st.divider()

                st.subheader(
                    "Intervention Validation"
                )

                st.dataframe(
                    intervention_validation,
                    use_container_width=True,
                    hide_index=True
                )

            else:

                st.info(
                    "Intervention validation file is currently empty. "
                    "No intervention validation results were generated."
                )

        except pd.errors.EmptyDataError:

            st.info(
                "Intervention validation file is currently empty. "
                "No intervention validation results were generated."
            )

        except Exception as e:

            st.warning(
                f"Could not read intervention validation file: {e}"
            )

    # --------------------------------------------------------
    # VALIDATION EXPLANATION
    # --------------------------------------------------------

    st.divider()

    st.subheader(
        "What This Validation Means"
    )

    st.markdown(
        """
        The validation results compare the model's predicted shade
        classification with the observed shade classification.

        **Match = 1 → Model prediction agrees with the observed result.**

        **Match = 0 → Model prediction does not agree with the observed result.**

        This helps demonstrate that the environmental model is producing
        consistent results against the available validation cases.
        """
    )


# ============================================================
# SIDEBAR FOOTER
# ============================================================

st.sidebar.divider()

st.sidebar.caption(
    "EcoTwin-X | Environmental Digital Twin"
)

st.sidebar.caption(
    "Heat • Pollution • Equity • Routing • Intervention • Time Machine"
)
