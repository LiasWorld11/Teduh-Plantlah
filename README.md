# Teduh&Plantlah
### GIS-Based Urban Tree Planting Decision Support System

**Developed for the Sime Darby Property University Hackathon 2026 — Township of Tomorrow**

---

## About the Project
- Geographic Information System (GIS)-based decision-support prototype designed to identify potential urban tree-planting locations based on satellite-derived land surface temperature, land-cover classification and mapped infrastructure constraints.
- Aims to support data-informed urban greening by identifying areas experiencing higher surface temperatures and highlighting locations worth investigating for tree planting.

## Key Features

### 1. Interactive GIS Visualization

Display geographical features such as walking networks, pedestrian corridors, buildings and bus stops.

### 2. Satellite-Based Heat Analysis

Integrates Landsat-derived Land Surface Temperature (LST) data to visualize urban surface heat patterns and identify relatively hotter locations.

### 3. Infrastructure Screening

Uses geographic buffers around mapped vehicle-road centerlines and building footprints to exclude potentially conflicting candidate locations.

### 4. Heat-Driven Candidate Generation

Generates candidate inspection locations throughout a **500 m study radius**, evaluates temperature conditions and retains spatially locations 

### 5. Land-Cover Suitability Assessment

Incorporates ESA WorldCover classification data to distinguish preliminary planting-ground opportunities 

### 6. Planting Priority Scoring

Calculates a normalized heat-need score to help prioritize candidate locations according to satellite-derived surface temperatures.

### 7. Preliminary Tree-Species Suggestions

Provides a conditional shortlist of urban tree species for potential planting-ground locations. 

### 8. Planting Decision Dashboard

Displays candidate rankings, land-cover classifications, heat scores and planting assessments through an interactive decision-support dashboard.

## Study Areas

The current prototype focuses on four locations in Penang, Malaysia:

- Bayan Lepas
- Dato Keramat
- Ayer Itam
- Bayan Baru

## Technology Stack

| Category | Technologies |
|---|---|
| Programming | Python |
| Web application | Streamlit |
| Interactive mapping | Folium, Streamlit-Folium |
| Geospatial analysis | GeoPandas, Shapely, PyProj |
| Raster processing | Rasterio, NumPy |
| Geographic features | OpenStreetMap |
| Satellite temperature | Landsat 8/9 Collection 2 Level-2 |
| Land-cover classification | ESA WorldCover 2021 |
| Data preparation | Google Earth Engine |

## Installation and Local Execution

Clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/Teduh-Plantlah.git
cd Teduh-Plantlah
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
python -m streamlit run app.py
```

Ensure the required preprocessed geographic datasets are available in the `data/` directory.

## Data Sources

- **OpenStreetMap:** Geographic features, including roads, building footprints, pedestrian corridors and bus stops.
- **USGS Landsat 8/9:** Satellite-derived land surface temperature data, processed using Google Earth Engine.
- **ESA WorldCover 2021:** Satellite-based land-cover classification data.

## Limitations

Teduh&Plantlah is a **hackathon proof of concept**, not a certified tree-planting or engineering assessment system.

Important limitations include:

- Land surface temperature is not equivalent to ambient air temperature.
- Satellite observations do not provide exact tree-level planting conditions.
- Historical land-cover classifications may not reflect current ground conditions.
- Mapped road buffers are based on road centerlines rather than verified road edges.
- Underground utilities, drainage, soil conditions, property ownership and planting permissions are not verified.
- Tree-species suggestions are preliminary and require site-specific assessment.
- Identified locations are inspection candidates, not approved planting sites.

Future development could integrate higher-resolution imagery, verified land ownership, soil suitability, infrastructure records and field-survey information.
**Teduh&Plantlah — Supporting cooler urban environments through data-informed urban greening.**
