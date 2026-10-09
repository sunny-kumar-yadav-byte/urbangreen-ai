# UrbanGreen AI Backend — v0.3.1

Urban Environmental Prioritization and Green Infrastructure Recommendation Engine.

Analyzes environmental vulnerability across urban grid cells using satellite surface temperatures, vegetation indices (NDVI), real OpenStreetMap building footprints, and road network exposure to recommend targeted urban greening interventions.

---

## 🌟 Capabilities & Features

### 1. Satellite & Geospatial Data Pipeline
- **Multi-Provider Architecture**:
  - **Google Earth Engine (`GEEProvider`)**: Acquires real 30m Sentinel-2 Surface Reflectance (`COPERNICUS/S2_SR_HARMONIZED`) for NDVI and Landsat-8/9 Level 2 thermal data (`LANDSAT/LC08/C02/T1_L2`) for Land Surface Temperature (LST in °C).
  - **Open Geospatial & Satellite Reanalysis (`OpenGeospatialProvider`)**:
    - **Real Building Coverage (`built_up`)**: Retrieves genuine building footprints via OpenStreetMap Overpass (`way["building"]`), constructs Shapely polygons, projects to Cartesian metres (UTM via PyProj), and calculates the exact proportion of each grid cell covered by building footprints.
    - **Real Road Density (`road_density`)**: Retrieves genuine road networks via OpenStreetMap Overpass (`way["highway"]`), constructs Shapely LineStrings, projects to metres, and computes road length in $\text{km}/\text{km}^2$, normalized against an urban benchmark ceiling ($25.0\ \text{km}/\text{km}^2$).
    - **Live Regional Surface Temperature (`lst_c`)**: Fetches daytime peak temperatures from Copernicus ERA5 reanalysis via Open-Meteo.
    - **Estimated Features (`ndvi`, `green_area`)**: Explicitly disclosed as heuristically modeled in open mode until multispectral satellite rasters are queried.
  - **Synthetic Benchmark (`DummyProvider`)**: 500-zone reproducible benchmark dataset for testing and offline development via `force_synthetic: true`.
- **Dynamic Spatial Grid Generation**:
  - Automatically geocodes cities via OpenStreetMap Nominatim.
  - Subdivides the bounding box into regular polygon grid cells (default 500m x 500m) with Shapely.
  - Generates authentic GeoJSON `Polygon` exterior ring coordinates for GIS mapping.

### 2. Environmental Scoring & Decision Engine
- **Cross-City Reference Normalization**:
  - Fixed geographic reference bounds (`LST: 18°C–48°C`, `NDVI: -0.1–0.85`) allow meaningful, objective priority comparison across different cities.
  - Also supports `dataset_relative` (MinMaxScaler) for local relative ranking.
- **Rule-Based Weighted Prioritization**:
  - Weighted multi-criteria decision formula:
    $$\text{Priority} = 0.35 \times \text{Heat} + 0.25 \times \text{BuiltUp} + 0.15 \times \text{RoadDensity} + 0.15 \times \text{Exposure} + 0.10 \times \text{LowVegetation}$$
  - Classifies zones into `Low` (< 0.33), `Medium` (0.33–0.66), and `High` (≥ 0.66).
  - *(Explicitly identified as a rule-based decision model; not a trained machine learning model).*

### 3. Green Intervention Recommendations
- Tiered recommendations with action categories, urgency levels (`Critical`, `High`, `Medium`, `Maintenance`), and rationales:
  - **Tree Canopy Expansion**: For extreme surface heat and sparse vegetation canopy.
  - **Cool Roofs & High-Albedo Surfaces**: For high thermal absorption in dense built-up zones.
  - **Shaded Pedestrian & Mobility Corridors**: For high road density lacking vegetative buffers.
  - **Pocket Parks & Micro-Forests (Miyawaki Method)**: For neighborhoods with < 20% green area.
  - **Permeable Pavements & Bioswales**: For impervious zones with high runoff potential.
  - **Canopy Stewardship & Maintenance**: For stable, well-vegetated baselines.

### 4. Interactive What-If Scenarios
- Recalculates priority scores and updates recommendation tiers based on simulated changes (e.g. reducing heat by 20% or increasing NDVI by 0.3).

### 5. External GIS Ingestion
- `POST /ingest-gis` accepts pre-computed spatial zones from QGIS, ArcGIS, or custom pipelines with automated validation.

---

## 🚀 Quickstart & Setup

### 1. Installation
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 2. Configure Environment (Optional)
Copy `.env.example` to `.env` to configure Google Earth Engine or adjust weights:
```powershell
Copy-Item .env.example .env
```

If Google Earth Engine credentials are not configured, the backend automatically operates using the **Open Geospatial & Satellite Reanalysis** provider with zero configuration needed.

### 3. Run Development Server
```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Interactive API Documentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 🛰️ Google Earth Engine Setup (Optional)

If you have a Google Cloud Project with the Earth Engine API enabled:
1. Create a service account in the GCP Console and grant it the **Earth Engine Resource Viewer / User** role.
2. Download the JSON key file and place it in the project directory.
3. In your `.env` file, set:
   ```env
   EE_PROJECT_ID=your-gcp-project-id
   EE_SERVICE_ACCOUNT=your-sa-name@your-project.iam.gserviceaccount.com
   EE_PRIVATE_KEY_FILE=./service_account_key.json
   ```
4. Verify provider readiness via `GET /satellite/status`.

---

## 📡 API Endpoints Reference

| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/` | `GET` | Service status, active version, and satellite provider readiness |
| `/health` | `GET` | Health check (`{"status": "healthy"}`) |
| `/satellite/status` | `GET` | Diagnostic status of GEE, Open Geospatial, and Dummy providers |
| `/analyze-city` | `POST` | Geocodes city, builds grid, acquires satellite data, scores, and returns zones |
| `/zones` | `GET` | Filter analyzed zones by category (`Low`, `Medium`, `High`) and limit |
| `/zones.geojson` | `GET` | GeoJSON `FeatureCollection` with `polygon` or `point` geometries |
| `/what-if` | `POST` | Simulate indicator adjustments on a zone |
| `/ingest-gis` | `POST` | Ingest external shapefile/GIS zone metrics directly |

---

## 🧪 Testing

Run the full automated test suite (23 unit and integration tests):
```powershell
.\.venv\Scripts\python.exe -m pytest
```

---

## ⚠️ Transparent Limitations & Disclosure

1. **Building & Road Measurements vs. Rate Limits**:
   - Building coverage (`built_up`) and road density (`road_density`) are calculated directly from OpenStreetMap vector geometries intersected with the grid polygons using projected metres.
   - If the public Overpass API experiences rate limits (HTTP 429) or gateway timeouts, the provider falls back gracefully and explicitly records the failure in `metadata.warnings`.
2. **Estimated Vegetation Indices in Open Mode**:
   - In `open_geospatial` mode, `ndvi` and `green_area` are **heuristically estimated** based on urban morphology. True pixel-by-pixel multispectral NDVI requires activating the `google_earth_engine` provider with Google Cloud credentials or uploading external GIS rasters.
3. **Rule-Based Prioritization, Not Trained ML**:
   - The prioritization score is a weighted decision rule derived from urban heat island and green infrastructure literature. No machine learning regression or neural network is claimed or trained.
4. **Screening Tool, Not Planting Prescription**:
   - Recommendations identify strategic intervention priorities. Actual field planting requires soil testing, species suitability, utility easement verification, and local community consultations.
