from pathlib import Path

import osmium
import geopandas as gpd

from shapely.geometry import Point, LineString, Polygon
from shapely.ops import transform
from pyproj import Transformer


PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"

PBF_FILE = DATA_DIR / "penang_study_areas.osm.pbf"

AREAS = {
    "Bayan Lepas": (5.296, 100.260),
    "Dato Keramat": (5.414, 100.311),
    "Ayer Itam": (5.402, 100.278),
    "Bayan Baru": (5.326, 100.285)
}

# Test only Bayan Lepas first.
SELECTED_AREAS = ["Dato Keramat"]

STUDY_RADIUS_M = 500

# Basic pedestrian-access filtering.
# This is a prototype, not a full OSMnx
# walk-network reconstruction.
WALKABLE_TYPES = {
    "footway", "pedestrian", "path", "steps",
    "living_street", "residential", "service",
    "tertiary", "secondary", "primary",
    "unclassified", "track"
}


class OfflineOSMExtractor(osmium.SimpleHandler):

    def __init__(self, selected_areas):
        super().__init__()

        self.selected_areas = {}

        to_metric = Transformer.from_crs(
            "EPSG:4326", "EPSG:32647",
            always_xy=True
        ).transform

        for name in selected_areas:

            lat, lon = AREAS[name]

            circle = transform(
                to_metric,
                Point(lon, lat)
            ).buffer(STUDY_RADIUS_M)

            # Convert study boundary back to GPS
            to_gps = Transformer.from_crs(
                "EPSG:32647", "EPSG:4326",
                always_xy=True
            ).transform

            circle_gps = transform(to_gps, circle)

            # Expanded bbox for fast filtering.
            minx, miny, maxx, maxy = (
                circle_gps.bounds
            )

            margin = 0.003

            self.selected_areas[name] = {
                "boundary": circle_gps,
                "bbox": (
                    minx - margin, miny - margin,
                    maxx + margin, maxy + margin
                ),
                "walking_network": [],
                "buildings": [],
                "bus_stops": []
            }

    def near_area(self, lon, lat, bbox):
        minx, miny, maxx, maxy = bbox

        return (
            minx <= lon <= maxx
            and miny <= lat <= maxy
        )

    def node(self, node):

        if node.tags.get("highway") != "bus_stop":
            return

        if not node.location.valid():
            return

        point = Point(
            node.location.lon,
            node.location.lat
        )

        for data in self.selected_areas.values():

            if data["boundary"].intersects(point):

                data["bus_stops"].append({
                    "osm_id": str(node.id),
                    "geometry": point
                })

    def way(self, way):

        highway = way.tags.get("highway")
        building = way.tags.get("building")

        is_walkable = (
            highway in WALKABLE_TYPES
            and way.tags.get("access") != "private"
            and way.tags.get("foot") != "no"
        )

        is_building = building is not None

        if not is_walkable and not is_building:
            return

        try:
            coords = [
                (n.lon, n.lat)
                for n in way.nodes
                if n.location.valid()
            ]
        except Exception:
            return

        if len(coords) < 2:
            return

        for data in self.selected_areas.values():

            # Quick approximate area check
            if not any(
                self.near_area(x, y, data["bbox"])
                for x, y in coords
            ):
                continue

            if is_walkable:

                line = LineString(coords)

                if data["boundary"].intersects(line):

                    data["walking_network"].append({
                        "osm_id": str(way.id),
                        "highway": highway,
                        "sidewalk": way.tags.get("sidewalk"),
                        "geometry": line
                    })

            if is_building:

                if (
                    len(coords) >= 4
                    and coords[0] == coords[-1]
                ):

                    polygon = Polygon(coords)

                    if not polygon.is_valid:
                        polygon = polygon.buffer(0)

                    if (
                        not polygon.is_empty
                        and data["boundary"].intersects(polygon)
                    ):

                        data["buildings"].append({
                            "osm_id": str(way.id),
                            "building": building,
                            "geometry": polygon
                        })


def export_area(name, data):

    filename = (
        name.lower().replace(" ", "_")
        + "_osm.gpkg"
    )

    output_path = DATA_DIR / filename

    if output_path.exists():
        print(
            f"Output already exists: {output_path}"
        )
        print("Delete or rename it before re-exporting.")
        return

    for layer in [
        "walking_network", "buildings", "bus_stops"
    ]:

        records = data[layer]

        if not records:
            print(f"{name}: {layer} has 0 features")
            continue

        gdf = gpd.GeoDataFrame(
            records,
            geometry="geometry",
            crs="EPSG:4326"
        )

        gdf.to_file(
            output_path,
            layer=layer,
            driver="GPKG"
        )

        print(
            f"{name}: saved {layer} "
            f"({len(gdf)} features)"
        )

    print(f"Output: {output_path}")


if __name__ == "__main__":

    if not PBF_FILE.exists():
        raise FileNotFoundError(PBF_FILE)

    print("Reading local PBF file...")

    extractor = OfflineOSMExtractor(
        SELECTED_AREAS
    )

    # Reads local PBF, no Overpass requests.
    extractor.apply_file(
        str(PBF_FILE),
        locations=True
    )

    for area, data in extractor.selected_areas.items():
        export_area(area, data)

    print("\nOffline extraction completed!")
