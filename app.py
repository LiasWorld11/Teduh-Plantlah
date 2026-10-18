import streamlit as st
import folium
import time

from streamlit_folium import st_folium

from geo_engine import (
    load_local_osm_data,
    calculate_safety_buffers,
    identify_footpaths,
    identify_vehicle_roads,
    generate_heat_candidates
)

from heat_engine import (
    get_heat_overlay,
    get_heat_at_point,
    calculate_heat_need_score
)

from tree_engine import recommend_tree_species

# ==========================================
# SIDEBAR
# ==========================================

areas = {
    "Bayan Lepas": (5.296, 100.260),
    "Dato Keramat": (5.414, 100.311),
    "Ayer Itam": (5.402, 100.278),
    "Bayan Baru": (5.326, 100.285)
}

with st.sidebar:

   st.title("🌳 Teduh&Plantlah")
   st.caption("Urban Tree Siting & Pedestrian Shade Analysis")

   st.divider()

   st.subheader("Analysis Controls")

   area = st.selectbox(
        "Select Area",
        list(areas.keys())
    )

   distance = 500

   st.divider()

   st.subheader("Tree Planting Planning")
   st.caption("Safety Consideration")

   road_setback = st.slider(
        "Network Buffer (m)",
        2.5, 10.0, 2.5, 0.5
    )

   building_setback = st.slider(
        "Building Buffer (m)",
        3.0, 10.0, 3.0, 0.5
    )

center_point = areas[area]

st.markdown("""
<style>
    [data-testid="stSidebar"] {
        min-width: 280px;
        max-width: 280px;
    }

    .block-container {
        padding-top: 1rem;
        padding-bottom: 0rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# CACHED OSM DATA
# ==========================================

@st.cache_data(show_spinner=False)
def get_osm_data(selected_area):
    return load_local_osm_data(selected_area)


with st.spinner("Preparing GIS layers..."):
    try:
        start = time.perf_counter()

        edges, buildings, bus_stops = get_osm_data(area)
        
        # Select mapped vehicular roads for road buffering.
        vehicle_roads = identify_vehicle_roads(edges)
        
        # Buffer vehicle-road centerlines and buildings.
        road_buffers, building_buffers = (
            calculate_safety_buffers(
                vehicle_roads,
                buildings,
                road_setback,
                building_setback
            )
        )

    except Exception as error:
        st.error("Unable to prepare GIS data.")
        st.exception(error)
        st.stop()

# Main Page 
st.set_page_config(layout="wide")
# Main Map
footpaths = identify_footpaths(edges)

# ==========================================
# WHOLE-AREA TREE PLANTING CANDIDATES
# ==========================================

screened_candidates = generate_heat_candidates(
    area=area,
    center_point=center_point,
    road_buffers=road_buffers,
    building_buffers=building_buffers,
    study_radius_m=distance,
    grid_spacing_m=30,
    min_separation_m=60,
    max_candidates=25
)

print(
    "[DEBUG] Candidate count:",
    len(screened_candidates)
)

print(
    "[DEBUG] Available columns:",
    screened_candidates.columns.tolist()
)

if not screened_candidates.empty:
    print(
        "[PLANTING ASSESSMENTS]\n",
        screened_candidates[
            [
                "candidate_id",
                "lst_c",
                "landcover_class",
                "planting_assessment"
            ]
        ].to_string(index=False)
    )
    

# ==========================================
# LAND-COVER SUITABILITY ASSESSMENT
# ==========================================

print(
    f"[HEAT CANDIDATES] {area}: "
    f"{len(screened_candidates)} inspection points"
)


m = folium.Map(
    
    location=center_point,
    zoom_start=16,
    tiles="OpenStreetMap",
    control_scale=True,
    zoom_control=True,
    scrollWheelZoom=True,
    prefer_canvas=True
)

# SATELLITE HEATMAP LAYER

@st.cache_data(show_spinner=False)
def load_heat_overlay(selected_area):
    return get_heat_overlay(selected_area)

try:
    start = time.perf_counter()

    heat_image, heat_bounds = load_heat_overlay(area)
    
    print(
        f"[PERFORMANCE] Heatmap ({area}): "
        f"{time.perf_counter() - start:.2f}s"
    )

    folium.raster_layers.ImageOverlay(
        image=heat_image,
        bounds=heat_bounds,
        name="Landsat Surface Temperature (2026)",
        opacity=0.75,
        show=True,
        interactive=False
    ).add_to(m)

except (FileNotFoundError, OSError, KeyError) as error:
    st.warning(
        f"Heatmap unavailable for {area}: {error}"
    )


# Walking-accessible network
folium.GeoJson(
    edges.to_json(),
    name="Walking Network",
    style_function=lambda feature: {
        "color": "#2584E9",
        "weight": 2.5,
        "opacity": 0.85
    }
).add_to(m)

#Pedestrian Corridors 
if not footpaths.empty:

    folium.GeoJson(
        footpaths.to_json(),
        name="Dedicated Pedestrian Paths",
        show=True,
        style_function=lambda feature: {
            "color": "#00E5FF",
            "weight": 5,
            "opacity": 1
        },
        tooltip="Dedicated Pedestrian Path"
    ).add_to(m)

# Building footprints
if not buildings.empty:
    folium.GeoJson(
        buildings.to_json(),
        name="Buildings",
        style_function=lambda feature: {
            "color": "#E69F30",
            "weight": 1,
            "fillColor": "#E69F30",
            "fillOpacity": 0.35
        }
    ).add_to(m)


# Bus stop locations
for _, stop in bus_stops.iterrows():

    point = stop.geometry

    if point.geom_type != "Point":
        point = point.representative_point()

    folium.CircleMarker(
        location=[point.y, point.x],
        radius=6,
        color="#800080",
        fill=True,
        fill_color="#800080",
        fill_opacity=0.95,
        tooltip="Mapped Bus Stop"
    ).add_to(m)


# Network exclusion buffer
if not road_buffers.empty:
    folium.GeoJson(
        road_buffers.to_json(),
        name="Network Exclusion Buffers",
        show=False,
        style_function=lambda feature: {
            "color": "#E53935",
            "weight": 1,
            "fillColor": "#E53935",
            "fillOpacity": 0.25
        }
    ).add_to(m)


# Building exclusion buffer
if not building_buffers.empty:
    folium.GeoJson(
        building_buffers.to_json(),
        name="Building Exclusion Buffers",
        show=True,
        style_function=lambda feature: {
            "color": "#E75D79",
            "weight": 1,
            "fillColor": "#E75D79",
            "fillOpacity": 0.30
        }
    ).add_to(m)

# ==========================================
# HEAT-PRIORITIZED INSPECTION MARKERS
# ==========================================

candidate_layer = folium.FeatureGroup(
    name="Heat-Priority Planting Candidates",
    show=True
)

for _, row in screened_candidates.iterrows():

    point = row.geometry
    
    # Generate a recommendation from the site's assessment
    recommendation = recommend_tree_species(
        row["planting_assessment"]
    )

    # Prepare species information for the popup
    if recommendation["species"]:
        species_html = "".join(
            f"<li><b>{tree['common_name']}</b> "
            f"(<i>{tree['scientific_name']}</i>) "
            f"— {tree['size_class']}</li>"
            for tree in recommendation["species"]
        )

        species_html = f"<ul>{species_html}</ul>"

    else:
        species_html = (
            "<p>No tree species recommended "
            "until site suitability is verified.</p>"
        )

    # Color based on relative heat-priority score
    score = float(row["heat_need_score"])

    if score >= 0.75:
        marker_color = "#5B1018"
    elif score >= 0.60:
        marker_color = "#B54A2B"
    elif score >= 0.45:
        marker_color = "#DB975A"
    elif score >= 0.30:
        marker_color = "#EACB9B"
    else:
        marker_color = "#E5E7EB"
    
    popup_html = f"""
    <div style="font-family:Arial; width:260px;">
    
        <!-- Tree Planting Prediction -->
        <b>Candidate {row['candidate_id']}</b>
        <hr>
    
        <!-- Land Cover Classification -->
        <b>Land Cover:</b> {row['landcover_class']}<br>
        <b>Planting Assessment:</b>
        {row['planting_assessment'].replace('_', ' ').title()}<br>
    
        <!-- Tree Recommendation -->
        <hr>
        <b>Tree Recommendation:</b><br>
        <b>Status:</b>
        {recommendation['status'].replace('_', ' ').title()}<br>
        {species_html}
    
        <p style="font-size:11px;color:#666;">
            {recommendation['reason']}
        </p>
        <hr>
    
        <!-- Heat Temperature -->
        <b>Landsat LST:</b> {row['lst_c']:.2f}°C<br>
        <b>Heat Need Score:</b>
        {row['heat_need_score']:.3f}<br>
    
        <!-- Geographic Location -->
        <b>Latitude:</b> {point.y:.6f}<br>
        <b>Longitude:</b> {point.x:.6f}<br>
        <hr>
    
    </div>
    """

    folium.CircleMarker(
        location=[point.y, point.x],
        radius=7,
        color="white",
        weight=2,
        fill=True,
        fill_color=marker_color,        
        fill_opacity=0.95,
        tooltip=(
            f"{row['candidate_id']} | "
            f"LST {row['lst_c']:.1f}°C"
        ),
        popup=folium.Popup(
            popup_html,
            max_width=320
        )
    ).add_to(candidate_layer)

candidate_layer.add_to(m)

# ==========================================
# 6. FLOATING MAP PANELS
# ==========================================

# These panels are embedded inside Folium's
# map iframe, rather than placed in separate
# Streamlit columns.

legend_html = """
<details style="
    position:fixed;
    bottom:35px;
    right:15px;
    z-index:9999;
    background:#17231e;
    color:white;
    padding:12px;
    border-radius:10px;
    width:240px;
    box-shadow:0 3px 12px rgba(0,0,0,0.35);
    font-family:Arial,sans-serif;
    font-size:13px;
">
<summary style="cursor:pointer;font-weight:bold;">
    Map Legend
</summary>

<div style="padding-top:12px;line-height:2.3;">
    <span style="color:#2584E9;">■</span>
    Walking Network<br>
    
    <span style="color:#00E5FF;">■</span>
    Dedicated Pedestrian Paths<br>

    <span style="color:#E69F30;">■</span>
    Buildings<br>

    <span style="color:#800080;">●</span>
    Bus Stops<br>

    <span style="color:#E53935;">■</span>
    Network Exclusion<br>

    <span style="color:#E75D79;">■</span>
    Building Exclusion

</div>
</details>
"""

m.get_root().html.add_child(
    folium.Element(legend_html)
)


# Floating GIS overview
overview_html = f"""
<details style="
    position:fixed;
    top:78px;
    left:12px;
    z-index:9999;
    background:#17231e;
    color:white;
    padding:12px;
    border-radius:10px;
    min-width:190px;
    box-shadow:0 3px 12px rgba(0,0,0,0.35);
    font-family:Arial,sans-serif;
    font-size:13px;
">
<summary style="cursor:pointer;font-weight:bold;">
    GIS Overview
</summary>

<div style="padding-top:12px;line-height:2;">
    <b>Walking edges:</b> {len(edges)}<br>
    <b>Buildings:</b> {len(buildings)}<br>
    <b>Bus stops:</b> {len(bus_stops)}<br>
    <b>Study area:</b> {area}
</div>
</details>
"""

m.get_root().html.add_child(
    folium.Element(overview_html)
)


# ==========================================
# 7. NATIVE MAP LAYERS CONTROL
# ==========================================

folium.LayerControl(
    collapsed=True,
    position="topright"
).add_to(m)

layer_control_css = """
    <style>
    .leaflet-top.leaflet-right {
        top: 50px !important;
    }
    
    .leaflet-control-layers-expanded {
        max-height: 55vh !important;
        overflow-y: auto !important;
        overflow-x: hidden !important;
    }
    </style>
"""

m.get_root().header.add_child(
    folium.Element(layer_control_css)
)

map_col, lst_col = st.columns(
    [15, 1],
    gap="small",
    vertical_alignment="top"
)

with map_col:
    st_folium(
        m,
        width=None,
        height=700,
        returned_objects=[],
        key=f"map_{area}_{distance}"
    )

#Right Taskbar: LST
with lst_col:

    lst_html = """
        <div style="
            background:#17231e;
            color:white;
            border-radius:10px;
            padding:18px 8px;
            margin-top:45px;
            font-family:Arial,sans-serif;
            display:flex;
            flex-direction:column;
            align-items:center;
            box-sizing:border-box;
        ">
        
        <div style="
            font-size:12px;
            font-weight:bold;
            margin-bottom:5px;
            text-align:center;
            line-height:1.4;
        ">
            Land Surface<br>
            Temperature
        </div>
        
        <div style="
            font-size:11px;
            color:#A8B8B0;
            margin-bottom:15px;
            text-align:center;
        ">
            LST (°C)
        </div>
        
        <div style="
            display:flex;
            align-items:center;
            justify-content:center;
            gap:8px;
        ">
            <div style="
                width:18px;
                height:260px;
                border-radius:5px;
                background:linear-gradient(
                    to top,
                    #2166AC 0%,
                    #67A9CF 25%,
                    #FFFFBF 50%,
                    #FDAE61 75%,
                    #D73027 100%
                );
            "></div>
    
            <div style="
                height:260px;
                display:flex;
                flex-direction:column;
                justify-content:space-between;
                font-size:11px;
            ">
                <span>55°</span>
                <span>45°</span>
                <span>35°</span>
                <span>25°</span>
            </div>
        </div>
    </div>
"""
    # Right Taskbar: Tree priority-based 
    st.html(lst_html)
    
    priority_html = """
        <div style="
            background:#17231e;
            color:white;
            border-radius:10px;
            padding:18px 8px;
            margin-top:10px;
            font-family:Arial,sans-serif;
            display:flex;
            flex-direction:column;
            align-items:center;
            box-sizing:border-box;
        ">

        <div style="
            font-size:12px;
            font-weight:bold;
            text-align:center;
            line-height:1.4;
            margin-bottom:6px;
        ">
            Planting<br>
            Priority
        </div>

        <div style="
            font-size:11px;
            color:#A8B8B0;
            text-align:center;
            margin-bottom:15px;
        ">
            Heat Score
        </div>

        <div style="
            display:flex;
            align-items:center;
            justify-content:center;
            gap:6px;
        ">

            <div style="
                width:18px;
                height:220px;
                border-radius:5px;
                background:linear-gradient(
                    to top,
                    #E5E7EB 0%,
                    #EACB9B 30%,
                    #DB975A 45%,
                    #B54A2B 60%,
                    #5B1018 75%
                );
            "></div>

            <div style="
                height:220px;
                display:flex;
                flex-direction:column;
                justify-content:space-between;
                font-size:11px;
            ">
                <span>1.00</span>
                <span>0.75</span>
                <span>0.50</span>
                <span>0.25</span>
                <span>0.00</span>
            </div>

        </div>
    </div>
    """

    st.html(priority_html)


# ==========================================
# PLANTING DECISION DASHBOARD
# ==========================================
st.divider()
st.subheader("Planting Decision Dashboard")
st.caption(
    f"{area} | {distance} m study radius | "
    "Preliminary GIS screening"
)

if screened_candidates.empty:
    st.info("No planting inspection candidates found.")

else:
    dashboard = screened_candidates.copy()

    # Count the different planting assessments
    total = len(dashboard)

    potential = (
        dashboard["planting_assessment"]
        == "POTENTIAL_GROUND"
    ).sum()

    engineering = (
        dashboard["planting_assessment"]
        == "ENGINEERING_ASSESSMENT"
    ).sum()

    other = total - potential - engineering

    # Summary 
    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Inspection Candidates", total)
    col2.metric("Potential Ground", int(potential))
    col3.metric("Engineering Review", int(engineering))
    col4.metric("Other Assessments", int(other))

    st.caption(
        "Potential ground does not mean approved for planting. "
        "All locations require field verification."
    )
    # Candidate filtering 
    st.markdown("#### Candidate Rankings")

    filter_option = st.selectbox(
        "Filter by planting assessment",
        [
            "All Candidates",
            "Potential Ground",
            "Engineering Assessment",
            "Other Assessments"
        ],
        key="candidate_filter"
    )

    if filter_option == "Potential Ground":
        dashboard = dashboard[
            dashboard["planting_assessment"]
            == "POTENTIAL_GROUND"
        ]

    elif filter_option == "Engineering Assessment":
        dashboard = dashboard[
            dashboard["planting_assessment"]
            == "ENGINEERING_ASSESSMENT"
        ]

    elif filter_option == "Other Assessments":
        dashboard = dashboard[
            ~dashboard["planting_assessment"].isin([
                "POTENTIAL_GROUND",
                "ENGINEERING_ASSESSMENT"
            ])
        ]

    # Highest heat score first within the filter.
    dashboard = dashboard.sort_values(
        "heat_need_score",
        ascending=False
    )
    
    # Candidate table 
    display_table = dashboard[
        [
            "candidate_id",
            "lst_c",
            "heat_need_score",
            "landcover_class",
            "planting_assessment"
        ]
    ].copy()

    display_table.columns = [
        "Candidate",
        "LST (°C)",
        "Heat Score",
        "Land Cover",
        "Planting Assessment"
    ]

    st.dataframe(
        display_table,
        hide_index=True,
        use_container_width=True
    )

    # Individual tree details 
    if not dashboard.empty:

        st.markdown("#### Candidate Details")

        selected_id = st.selectbox(
            "Select candidate",
            dashboard["candidate_id"].tolist(),
            key="candidate_details"
        )

        selected = dashboard[
            dashboard["candidate_id"] == selected_id
        ].iloc[0]

        st.write(
            "**Land Cover:**",
            selected["landcover_class"]
        )

        st.write(
            "**Planting Assessment:**",
            selected["planting_assessment"]
            .replace("_", " ").title()
        )

        st.write(
            "**Land Surface Temperature:**",
            f"{selected['lst_c']:.2f}°C"
        )

        st.write(
            "**Heat Priority Score:**",
            f"{selected['heat_need_score']:.3f}"
        )

        st.write(
            "**Coordinates:**",
            f"{selected.geometry.y:.6f}, "
            f"{selected.geometry.x:.6f}"
        )

        st.info(selected["screening_reason"])

    else:
        st.info("No candidates match the selected filter.")

