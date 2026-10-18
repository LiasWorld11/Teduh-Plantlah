from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import transform
# Heat map
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.transform import array_bounds

PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"

# All four study areas
LST_FILES = {
    "Bayan Lepas": DATA_DIR / "bayan_lepas_lst_2026.tif",
    "Dato Keramat": DATA_DIR / "dato_keramat_lst_2026.tif",
    "Ayer Itam": DATA_DIR / "ayer_itam_lst_2026.tif",
    "Bayan Baru": DATA_DIR / "bayan_baru_lst_2026.tif"
}

# Shared scoring reference for all study areas (not official)
HEAT_MIN_C = 25.0
HEAT_MAX_C = 55.0

# Print temperature statistics for a study area.
def inspect_lst_raster(area):

    with rasterio.open(LST_FILES[area]) as dataset:
        values = dataset.read(1, masked=True).compressed()
        values = values[np.isfinite(values)]

        if values.size == 0:
            print(f"{area}: No valid temperature pixels")
            return

        print(f"\n=== {area} ===")
        print("CRS:", dataset.crs)
        print("Raster size:", dataset.width, "x", dataset.height)
        print("Min:", round(float(values.min()), 2), "°C")
        print("Mean:", round(float(values.mean()), 2), "°C")
        print("Max:", round(float(values.max()), 2), "°C")


# Return temperature 
def get_heat_at_point(area, latitude, longitude):

    raster_path = LST_FILES[area]

    with rasterio.open(raster_path) as dataset:

        x, y = transform(
            "EPSG:4326",
            dataset.crs,
            [longitude],
            [latitude]
        )

        # Reject coordinates outside this area's raster
        if not (
            dataset.bounds.left <= x[0] < dataset.bounds.right
            and dataset.bounds.bottom < y[0] <= dataset.bounds.top
        ):
            return None

        sample = next(
            dataset.sample([(x[0], y[0])], masked=True)
        )

        value = sample[0]

        if np.ma.is_masked(value):
            return None

        temperature = float(value)

        if not np.isfinite(temperature):
            return None

        return round(temperature, 2)

# Normalize temperature to 0-1 
def calculate_heat_need_score(temperature):

    if temperature is None or not np.isfinite(temperature):
        return None

    score = (
        (temperature - HEAT_MIN_C)
        / (HEAT_MAX_C - HEAT_MIN_C)
    )

    return round(float(np.clip(score, 0, 1)), 3)

# ==========================================
# LAND SURFACE TEMPERATURE MAP OVERLAY
# ==========================================

def get_heat_overlay(area):
    raster_path = LST_FILES[area]

    with rasterio.open(raster_path) as src:

        dst_transform, width, height = (
            calculate_default_transform(
                src.crs,
                "EPSG:4326",
                src.width,
                src.height,
                *src.bounds
            )
        )

        destination = np.full(
            (height, width),
            np.nan,
            dtype=np.float32
        )

        source = src.read(1, masked=True)
        source = source.filled(np.nan).astype("float32")

        reproject(
            source=source,
            destination=destination,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=np.nan,
            dst_transform=dst_transform,
            dst_crs="EPSG:4326",
            dst_nodata=np.nan,
            resampling=Resampling.nearest
        )

    normalized = np.clip(
        (destination - HEAT_MIN_C)
        / (HEAT_MAX_C - HEAT_MIN_C),
        0,
        1
    )

    # Blue -> cyan -> yellow -> orange -> red
    palette = np.array([
        [33, 102, 172],
        [103, 169, 207],
        [255, 255, 191],
        [253, 174, 97],
        [215, 48, 39]
    ])

    rgba = np.zeros(
        (height, width, 4),
        dtype=np.uint8
    )

    valid = np.isfinite(destination)

    if valid.any():
        positions = normalized[valid] * 4

        lower = np.minimum(
            positions.astype(int), 3
        )

        fraction = (
            positions - lower
        )[:, None]

        colors = (
            palette[lower] * (1 - fraction)
            + palette[lower + 1] * fraction
        )

        rgba[valid, :3] = colors.astype(np.uint8)
        rgba[valid, 3] = 180

    # Convert geographic bounds into diff direction
    west, south, east, north = array_bounds(
        height, width, dst_transform
    )

    bounds = [
        [south, west],
        [north, east]
    ]

    return rgba, bounds


if __name__ == "__main__":

    centers = {
    "Bayan Lepas": (5.296, 100.260),
    "Dato Keramat": (5.414, 100.311),
    "Ayer Itam": (5.402, 100.278),
    "George Town": (5.414, 100.329)
    }

    for area, (lat, lon) in centers.items():

        inspect_lst_raster(area)

        temperature = get_heat_at_point(
            area, lat, lon
        )

        score = calculate_heat_need_score(temperature)

        print("Center LST:", temperature, "°C")
        print("Heat Need Score:", score)
