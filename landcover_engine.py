from pathlib import Path
from pyproj import Transformer
import numpy as np
import rasterio


DATA_DIR = Path(__file__).resolve().parent / "data"

LANDCOVER_FILES = {
    "Dato Keramat": DATA_DIR / "dato_keramat_landcover_2021.tif",
    "Bayan Lepas": DATA_DIR / "bayan_lepas_landcover_2021.tif",
    "Ayer Itam": DATA_DIR / "ayer_itam_landcover_2021.tif",
    "Bayan Baru": DATA_DIR / "bayan_baru_landcover_2021.tif"
}

# Official ESA WorldCover classification codes
LANDCOVER_CLASSES = {
    10: "Tree cover",
    20: "Shrubland",
    30: "Grassland",
    40: "Cropland",
    50: "Built-up",
    60: "Bare / sparse vegetation",
    70: "Snow / ice",
    80: "Permanent water",
    90: "Herbaceous wetland",
    95: "Mangroves",
    100: "Moss / lichen"
}

# Inspect valid land-cover classes in a raster
def inspect_landcover(area):
    raster_path = LANDCOVER_FILES[area]

    with rasterio.open(raster_path) as dataset:
        values = dataset.read(1, masked=True).compressed()

        # WorldCover class 0 is not a valid land-cover category
        values = values[values != 0]

        codes, counts = np.unique(
            values,
            return_counts=True
        )

        print(f"\n=== {area} LAND COVER ===")
        print("CRS:", dataset.crs)
        print("Raster size:", dataset.width, "x", dataset.height)

        print("\nLand-cover distribution:")

        for code, count in zip(codes, counts):
            name = LANDCOVER_CLASSES.get(
                int(code),
                "Unknown class"
            )

            print(
                f"{int(code)} - {name}: "
                f"{int(count)} pixels"
            )

# Return the ESA WorldCover classification at a GPS point
def get_landcover_at_point(area, latitude, longitude):

    raster_path = LANDCOVER_FILES[area]

    with rasterio.open(raster_path) as dataset:

        transformer = Transformer.from_crs(
            "EPSG:4326",
            dataset.crs,
            always_xy=True
        )

        x, y = transformer.transform(longitude, latitude)

        value = next(
            dataset.sample([(x, y)], masked=True)
        )[0]

        if np.ma.is_masked(value):
            return None

        code = int(value)

        if code not in LANDCOVER_CLASSES:
            return None

        return code

# Preliminary planting assessment based on ESA lassification
def assess_planting_suitability(landcover_code):

    if landcover_code in (30, 60):
        return "POTENTIAL_GROUND"

    elif landcover_code == 50:
        return "ENGINEERING_ASSESSMENT"

    elif landcover_code == 10:
        return "EXISTING_TREE_COVER"

    elif landcover_code in (80, 90, 95):
        return "EXCLUDED_LANDCOVER"

    elif landcover_code is None:
        return "INSUFFICIENT_DATA"

    else:
        return "LAND_USE_VERIFICATION"


if __name__ == "__main__":
    inspect_landcover("Dato Keramat")
