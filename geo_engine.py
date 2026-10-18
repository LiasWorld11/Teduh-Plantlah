import osmnx as ox
import geopandas as gpd

import numpy as np
import rasterio

from pathlib import Path

from shapely.geometry import Point
from pyproj import Transformer

from heat_engine import LST_FILES, calculate_heat_need_score

from landcover_engine import (
    LANDCOVER_FILES,
    LANDCOVER_CLASSES,
    get_landcover_at_point,
    assess_planting_suitability
)

ox.settings.use_cache = True


# Retrieve data 
def load_osm_data(center_point, distance=500):

    # Walking network
    walking_graph = ox.graph.graph_from_point(
        center_point=center_point,
        dist=distance,
        network_type="walk"
    )

    nodes, edges = ox.convert.graph_to_gdfs(
        walking_graph
    )

    # Building footprints
    building_data = ox.features.features_from_point(
        center_point=center_point,
        tags={"building": True},
        dist=distance
    )

    buildings = building_data[
        building_data.geometry.geom_type.isin(
            ["Polygon", "MultiPolygon"]
        )
    ].copy()

    # Bus stops
    try:
        bus_stops = ox.features.features_from_point(
            center_point=center_point,
            tags={"highway": "bus_stop"},
            dist=distance
        )

    except ox._errors.InsufficientResponseError:
        bus_stops = gpd.GeoDataFrame(
            geometry=[],
            crs="EPSG:4326"
        )

    return edges, buildings, bus_stops

# ==========================================
# OFFLINE OSM DATA LOADER
# ==========================================

def load_local_osm_data(area):
    """
    Load locally saved OSM geographic layers.

    No Overpass API connection is required.
    """

    data_dir = Path(__file__).resolve().parent / "data"

    filename = (
        area.lower().replace(" ", "_") + "_osm.gpkg"
    )

    gpkg_path = data_dir / filename

    if not gpkg_path.exists():
        raise FileNotFoundError(
            f"Offline OSM file not found: {gpkg_path}"
        )

    edges = gpd.read_file(
        gpkg_path,
        layer="walking_network"
    )

    buildings = gpd.read_file(
        gpkg_path,
        layer="buildings"
    )

    bus_stops = gpd.read_file(
        gpkg_path,
        layer="bus_stops"
    )

    return edges, buildings, bus_stops


# ==========================================
# Infrastructure Exclusion Buffer Engine
# ==========================================

def calculate_safety_buffers(
    edges,
    buildings,
    road_setback,
    building_setback
):

    # Local projected CRS for Penang
    metric_crs = "EPSG:32647"

    # Convert geographic data to metres
    edges_m = edges.to_crs(metric_crs)
    buildings_m = buildings.to_crs(metric_crs)

    # Network-line buffers
    road_buffer_series = edges_m.geometry.buffer(
        road_setback
    )

    # Create building footprint buffers
    building_buffer_series = (
        buildings_m.geometry.buffer(building_setback)
    )

    # Merge overlapping polygons
    road_union = road_buffer_series.union_all()

    if buildings_m.empty:
        building_union = None
    else:
        building_union = building_buffer_series.union_all()

    # Convert results into GeoDataFrames
    road_buffers = gpd.GeoDataFrame(
        {"geometry": [road_union]},
        crs=metric_crs
    )

    if building_union is not None:
        building_buffers = gpd.GeoDataFrame(
            {"geometry": [building_union]},
            crs=metric_crs
        )
    else:
        building_buffers = gpd.GeoDataFrame(
            geometry=[],
            crs=metric_crs
        )

    # Convert back to GPS coordinates for display on Folium
    road_buffers = road_buffers.to_crs("EPSG:4326")
    building_buffers = building_buffers.to_crs("EPSG:4326")

    return road_buffers, building_buffers

# ==========================================
# PEDESTRIAN CLASSIFICATION
# ==========================================

def identify_footpaths(edges):
    
    if "highway" not in edges.columns:
        return edges.iloc[0:0].copy()

    def is_pedestrian_corridor(row):

        highway = row.get("highway", "")
        sidewalk = row.get("sidewalk", "")

        # Support string or list highway values.
        if isinstance(highway, (list, tuple, set)):
            highway_types = set(highway)
        else:
            highway_types = {str(highway)}

        # Stairways are not planting corridors.
        if "steps" in highway_types:
            return False

        # Dedicated pedestrian paths
        if highway_types.intersection(
            {"footway", "pedestrian"}
        ):
            return True

        # Explicitly mapped sidewalks
        if isinstance(sidewalk, str):
            sidewalk = sidewalk.lower().strip()

        sidewalk_values = {
            "yes", "both", "left", "right",
            "separate"
        }

        if sidewalk in sidewalk_values:
            return True

        return False

    mask = edges.apply(
        is_pedestrian_corridor,
        axis=1
    )

    return edges.loc[mask].copy()

# ==========================================
# VEHICULAR ROAD CLASSIFICATION
# ==========================================

def identify_vehicle_roads(edges):
    """
    Identify mapped roads generally used by vehicles.

    Uses OSM highway classifications.
    Returns a GeoDataFrame containing road lines.
    """

    vehicle_types = {
        "motorway",
        "trunk",
        "primary",
        "secondary",
        "tertiary",
        "residential",
        "service",
        "unclassified",
        "living_street"
    }

    if "highway" not in edges.columns:
        return edges.iloc[0:0].copy()

    def is_vehicle_road(value):
        if isinstance(value, (list, tuple, set)):
            return any(
                tag in vehicle_types for tag in value
            )

        return value in vehicle_types

    return edges.loc[
        edges["highway"].apply(is_vehicle_road)
    ].copy()

# ==========================================
# WHOLE-AREA HEAT-DRIVEN CANDIDATE ENGINE
# ==========================================

def generate_heat_candidates(
    area,
    center_point,
    road_buffers,
    building_buffers,
    study_radius_m=500,
    grid_spacing_m=30,
    min_separation_m=60,
    max_candidates=25
):

    metric_crs = "EPSG:32647"

    # Convert study center from GPS to metres
    to_metric = Transformer.from_crs(
        "EPSG:4326", metric_crs, always_xy=True
    )

    latitude, longitude = center_point

    cx, cy = to_metric.transform(
        longitude, latitude
    )

    # Combine known exclusion polygons
    roads_m = road_buffers.to_crs(metric_crs)
    buildings_m = building_buffers.to_crs(metric_crs)

    road_zone = (
        roads_m.geometry.union_all()
        if not roads_m.empty else None
    )

    building_zone = (
        buildings_m.geometry.union_all()
        if not buildings_m.empty else None
    )

    # Generate samples across the study circle
    grid_points = []

    start_x = cx - study_radius_m + grid_spacing_m / 2
    start_y = cy - study_radius_m + grid_spacing_m / 2

    for x in np.arange(
        start_x,
        cx + study_radius_m,
        grid_spacing_m
    ):
        for y in np.arange(
            start_y,
            cy + study_radius_m,
            grid_spacing_m
        ):

            if np.hypot(x - cx, y - cy) > study_radius_m:
                continue

            point = Point(x, y)

            # Preliminary infrastructure screening
            if road_zone is not None and road_zone.intersects(point):
                continue

            if building_zone is not None and building_zone.intersects(point):
                continue

            grid_points.append(point)

        columns = [
        "geometry",
        "candidate_id",
        "lst_c",
        "heat_need_score",
        "landcover_code",
        "landcover_class",
        "planting_assessment",
        "screening_status",
        "screening_reason"
    ]

    if not grid_points:
        return gpd.GeoDataFrame(
            columns=columns,
            geometry="geometry",
            crs="EPSG:4326"
        )

    # Read the Landsat raster once, not once per point
    with rasterio.open(LST_FILES[area]) as dataset:

        to_raster = Transformer.from_crs(
            metric_crs,
            dataset.crs,
            always_xy=True
        )

        raster_coords = [
            to_raster.transform(p.x, p.y)
            for p in grid_points
        ]

        samples = list(
            dataset.sample(
                raster_coords,
                masked=True
            )
        )

    
    # Attach temperature and land-cover information
    records = []

    landcover_available = (
        area in LANDCOVER_FILES
        and LANDCOVER_FILES[area].exists()
    )

    for point, sample in zip(grid_points, samples):

        value = sample[0]

        if np.ma.is_masked(value):
            continue

        temperature = float(value)

        if not np.isfinite(temperature):
            continue

        # Convert projected grid point to GPS
        to_gps = Transformer.from_crs(
            metric_crs,
            "EPSG:4326",
            always_xy=True
        )

        longitude, latitude = to_gps.transform(
            point.x, point.y
        )

        if landcover_available:
            code = get_landcover_at_point(
                area,
                latitude,
                longitude
            )
        else:
            code = None

        assessment = assess_planting_suitability(code)

        # Do not recommend water/wetland locations
        if assessment == "EXCLUDED_LANDCOVER":
            continue

        records.append({
            "geometry": point,
            "lst_c": round(temperature, 2),
            "heat_need_score":
                calculate_heat_need_score(temperature),
            "landcover_code": code,
            "landcover_class":
                LANDCOVER_CLASSES.get(code, "Unknown"),
            "planting_assessment": assessment,
            "screening_status": "NEEDS_VERIFICATION",
            "screening_reason":
                "Preliminary map-based assessment. "
                "Ground conditions, utilities, drainage "
                "and ownership require verification."
        })

    # Land-cover tree planting selection 
    
    # Preliminary categories, not confirmed planting permissions.
    ground_candidates = [
        r for r in records
        if r["planting_assessment"] == "POTENTIAL_GROUND"
    ]

    engineering_candidates = [
        r for r in records
        if r["planting_assessment"] == "ENGINEERING_ASSESSMENT"
    ]

    # Retain heat-priority inspection candidates
    unknown_candidates = [
        r for r in records
        if r["planting_assessment"] == "INSUFFICIENT_DATA"
    ]

    for group in (
        ground_candidates,
        engineering_candidates,
        unknown_candidates
    ):
        group.sort(
            key=lambda r: r["lst_c"],
            reverse=True
        )

    selected = []

    def add_spatially_separated(group, limit):
        added = 0

        for record in group:

            if len(selected) >= max_candidates:
                break

            if added >= limit:
                break

            point = record["geometry"]

            if any(
                point.distance(existing["geometry"])
                < min_separation_m
                for existing in selected
            ):
                continue

            selected.append(record)
            added += 1

    if landcover_available:

        # Prefer potential planting ground
        add_spatially_separated(
            ground_candidates,
            max_candidates
        )

        # Use remaining slots for engineered heat-intervention opportunities
        add_spatially_separated(
            engineering_candidates,
            max_candidates - len(selected)
        )

    else:
        add_spatially_separated(
            unknown_candidates,
            max_candidates
        )


    if not selected:
        return gpd.GeoDataFrame(
            columns=columns,
            geometry="geometry",
            crs="EPSG:4326"
        )

    result = gpd.GeoDataFrame(
        selected,
        geometry="geometry",
        crs=metric_crs
    )

    result["candidate_id"] = [
        f"C{i:02d}"
        for i in range(1, len(result) + 1)
    ]

    return result.to_crs("EPSG:4326")
