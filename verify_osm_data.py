from pathlib import Path
import geopandas as gpd
import pyogrio

DATA_DIR = Path(__file__).resolve().parent / "data"

# Existing areas 
areas = [
    "bayan_lepas",
    "dato_keramat",
    "ayer_itam",
    "bayan_baru"
]

for area in areas:
    path = DATA_DIR / f"{area}_osm.gpkg"

    print(f"\n=== {area.upper()} ===")

    if not path.exists():
        print("MISSING FILE")
        continue

    layers = pyogrio.list_layers(path)

    for layer_name, geometry_type in layers:
        data = gpd.read_file(path, layer=layer_name)

        print(
            f"{layer_name}: {len(data)} features "
            f"({geometry_type})"
        )
