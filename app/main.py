import logging
from typing import Dict, Any, Optional
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, status, Request
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from .config import WEIGHTS, PROJECT_ROOT
from .schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    DataSourceMetadata,
    WhatIfRequest,
    WhatIfResponse,
    IngestCustomZonesRequest,
    ZoneRecord,
    RecommendationDetail
)
from .pipeline import (
    run_analysis,
    save_results,
    build_geojson,
    generate_recommendations,
    generate_recommendation_details
)
from .services.geocoding import geocode_city_bbox
from .services.grid import generate_spatial_grid, GridCell
from .services.satellite import (
    acquire_environmental_data,
    gee_provider,
    open_provider,
    dummy_provider
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="UrbanGreen AI API",
    version="0.3.0",
    description=(
        "Urban Environmental Analysis & Green Infrastructure Planning Engine. "
        "Integrates satellite surface temperature, vegetation index (NDVI), OpenStreetMap "
        "impervious/road densities, spatial polygon grids, and rule-based green intervention planning."
    )
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)

# In-memory session cache for latest analysis (avoids recomputing across /zones and /zones.geojson)
_LATEST_ANALYSIS: Dict[str, Any] = {
    "df": None,
    "grid_cells": None,
    "city": None,
    "metadata": None
}

@app.get("/", tags=["System"])
def home(request: Request):
    accept = request.headers.get("accept", "")
    # If opened by a web browser, redirect directly to the interactive frontend dashboard
    if "text/html" in accept and "application/json" not in accept:
        return RedirectResponse(url="/ui")

    gee_ready, gee_msg = gee_provider.is_available()
    return {
        "message": "UrbanGreen AI API",
        "version": "0.3.0",
        "status": "ready",
        "docs": "/docs",
        "providers": {
            "google_earth_engine": {"available": gee_ready, "status": gee_msg},
            "open_geospatial": {"available": True, "status": "Ready (Satellite Reanalysis & OSM)"},
            "synthetic_demo": {"available": True, "status": "Ready"}
        }
    }

@app.get("/health", tags=["System"])
def health():
    return {"status": "healthy"}

@app.get("/satellite/status", tags=["Satellite"])
def satellite_status():
    """Inspects the availability and configuration of satellite data providers."""
    gee_ok, gee_msg = gee_provider.is_available()
    open_ok, open_msg = open_provider.is_available()
    return {
        "active_primary_provider": "google_earth_engine" if gee_ok else "open_geospatial",
        "providers": [
            {
                "name": "google_earth_engine",
                "available": gee_ok,
                "message": gee_msg,
                "resolution": "30m (Landsat & Sentinel-2)",
                "requires_credentials": True
            },
            {
                "name": "open_geospatial",
                "available": open_ok,
                "message": open_msg,
                "resolution": "Grid cell resolution (~100-500m)",
                "requires_credentials": False
            },
            {
                "name": "synthetic_dummy",
                "available": True,
                "message": "Synthetic demonstration dataset (500 zones)",
                "requires_credentials": False
            }
        ]
    }

@app.post("/analyze-city", response_model=AnalyzeResponse, tags=["Analysis"])
def analyze_city(request: AnalyzeRequest):
    """
    Analyzes environmental conditions for a city.
    Acquires satellite surface temperature, NDVI, and spatial indicators across a polygon grid,
    assigns priority scores, and recommends targeted green interventions.
    """
    try:
        if request.force_synthetic:
            # Synthetic demonstration mode
            df_raw, metadata = dummy_provider.acquire_features(request.city, (0, 0, 0, 0), [])
            grid_cells = None
        else:
            # 1. Geocode city bounds
            bbox = tuple(request.bbox) if request.bbox and len(request.bbox) == 4 else geocode_city_bbox(request.city)
            
            # 2. Generate polygon spatial grid
            grid_cells = generate_spatial_grid(bbox, target_grid_size_m=request.grid_size_m)
            
            # 3. Acquire satellite & geospatial features
            df_raw, metadata = acquire_environmental_data(
                city=request.city,
                bbox=bbox,
                grid_cells=grid_cells,
                force_synthetic=False
            )

        # 4. Run feature normalization and priority scoring
        analyzed_df = run_analysis(
            data=df_raw,
            normalization_method=request.normalization_method
        )
        
        # Save results to persistent disk
        save_results(analyzed_df)

        # Update session cache
        _LATEST_ANALYSIS["df"] = analyzed_df
        _LATEST_ANALYSIS["grid_cells"] = grid_cells
        _LATEST_ANALYSIS["city"] = request.city
        _LATEST_ANALYSIS["metadata"] = metadata

    except Exception as exc:
        logger.error(f"Analysis failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis pipeline error: {str(exc)}"
        ) from exc

    counts = analyzed_df["category"].value_counts()
    cell_polygon_map = {c.zone_id: c.polygon_coordinates for c in grid_cells} if grid_cells else {}

    zones = []
    for _, r in analyzed_df.iterrows():
        zid = str(r["zone_id"])
        
        # Structured recommendation items
        rec_details = [
            RecommendationDetail(**d)
            for d in r.get("recommendation_details", [])
        ]
        
        indicators = {
            k: round(float(r[k]), 4)
            for k in ["heat", "ndvi", "built_up", "road_density", "green_area", "exposure"]
            if k in r
        }
        
        raw_metrics = {
            "lst_c": round(float(r["lst_c"]), 2) if "lst_c" in r else None,
            "raw_ndvi": round(float(r["ndvi"]), 4) if "ndvi" in r else None
        }

        poly_coords = cell_polygon_map.get(zid)
        recs_list = r["recommendations"] if isinstance(r["recommendations"], list) else [str(r["recommendations"])]
        single_rec = recs_list[0] if len(recs_list) > 0 else "Maintain existing green cover"

        zones.append(ZoneRecord(
            zone_id=zid,
            lat=float(r["lat"]),
            lon=float(r["lon"]),
            priority_score=round(float(r["priority_score"]), 4),
            category=str(r["category"]),
            recommendations=recs_list,
            recommendation_details=rec_details,
            indicators=indicators,
            raw_metrics={k: v for k, v in raw_metrics.items() if v is not None},
            polygon_coordinates=poly_coords,
            # Frontend compatibility fields
            latitude=float(r["lat"]),
            longitude=float(r["lon"]),
            location=f"{request.city} - {zid}",
            locality=f"Grid Cell {zid}",
            grid_size=f"{request.grid_size_m}m × {request.grid_size_m}m",
            lst=raw_metrics.get("lst_c"),
            ndvi=indicators.get("ndvi"),
            built_up=indicators.get("built_up"),
            road_density=indicators.get("road_density"),
            priority=str(r["category"]).upper(),
            recommendation=single_rec,
            satellite_url=None
        ))

    # Priority zones for frontend display
    high_p_zones = [z for z in zones if z.category == "High"]
    if not high_p_zones:
        high_p_zones = sorted(zones, key=lambda z: z.priority_score, reverse=True)[:10]
    else:
        high_p_zones = sorted(high_p_zones, key=lambda z: z.priority_score, reverse=True)
    top_zone = high_p_zones[0] if high_p_zones else (zones[0] if zones else None)

    avg_lst = round(float(analyzed_df["lst_c"].mean()), 2) if "lst_c" in analyzed_df else None
    avg_ndvi = round(float(analyzed_df["ndvi"].mean()), 4) if "ndvi" in analyzed_df else None
    avg_built = round(float(analyzed_df["built_up"].mean()), 4) if "built_up" in analyzed_df else None
    priority_idx = round(float(analyzed_df["priority_score"].mean()), 4)

    return AnalyzeResponse(
        city=request.city,
        data_source=metadata.provider,
        synthetic_data=metadata.synthetic_data,
        metadata=metadata,
        total_zones=len(zones),
        summary={k: int(counts.get(k, 0)) for k in ["Low", "Medium", "High"]},
        zones=zones,
        notice=metadata.notice,
        # Frontend compatibility fields
        avg_lst=avg_lst,
        avg_ndvi=avg_ndvi,
        high_priority_zones=int(counts.get("High", 0)),
        priority_index=priority_idx,
        built_up=avg_built,
        zone=top_zone,
        high_priority_zone_list=high_p_zones
    )

@app.post("/ingest-gis", response_model=AnalyzeResponse, tags=["GIS Integration"])
def ingest_custom_gis(request: IngestCustomZonesRequest):
    """
    Ingests pre-computed GIS feature zones (e.g. from QGIS or ArcGIS),
    normalizes features, calculates priority scores, and generates green recommendations.
    """
    records = []
    cell_polygons = {}
    for z in request.zones:
        records.append({
            "zone_id": z.zone_id,
            "lat": z.lat,
            "lon": z.lon,
            "lst_c": z.lst_c,
            "ndvi": z.ndvi,
            "built_up": z.built_up,
            "road_density": z.road_density,
            "green_area": z.green_area,
            "exposure": z.exposure
        })
        if z.polygon_coordinates:
            cell_polygons[z.zone_id] = z.polygon_coordinates

    df_raw = pd.DataFrame(records)
    analyzed_df = run_analysis(data=df_raw, normalization_method=request.normalization_method)

    metadata = DataSourceMetadata(
        provider="user_provided_gis",
        synthetic_data=False,
        satellite_source="User GIS Ingestion Interface",
        resolution_meters=None,
        notice="Derived from user-supplied GIS and remote sensing features."
    )

    counts = analyzed_df["category"].value_counts()
    zones = []
    for _, r in analyzed_df.iterrows():
        zid = str(r["zone_id"])
        rec_details = [RecommendationDetail(**d) for d in r.get("recommendation_details", [])]
        recs_list = r["recommendations"] if isinstance(r["recommendations"], list) else [str(r["recommendations"])]
        single_rec = recs_list[0] if len(recs_list) > 0 else "Maintain existing green cover"
        indicators = {k: round(float(r[k]), 4) for k in ["heat", "ndvi", "built_up", "road_density", "green_area", "exposure"]}

        zones.append(ZoneRecord(
            zone_id=zid,
            lat=float(r["lat"]),
            lon=float(r["lon"]),
            priority_score=round(float(r["priority_score"]), 4),
            category=str(r["category"]),
            recommendations=recs_list,
            recommendation_details=rec_details,
            indicators=indicators,
            polygon_coordinates=cell_polygons.get(zid),
            # Frontend compatibility fields
            latitude=float(r["lat"]),
            longitude=float(r["lon"]),
            location=f"{request.city} - {zid}",
            locality=f"Zone {zid}",
            grid_size="Custom GIS",
            lst=round(float(r["lst_c"]), 2) if "lst_c" in r else None,
            ndvi=indicators.get("ndvi"),
            built_up=indicators.get("built_up"),
            road_density=indicators.get("road_density"),
            priority=str(r["category"]).upper(),
            recommendation=single_rec,
            satellite_url=None
        ))

    high_p_zones = [z for z in zones if z.category == "High"]
    if not high_p_zones:
        high_p_zones = sorted(zones, key=lambda z: z.priority_score, reverse=True)[:10]
    else:
        high_p_zones = sorted(high_p_zones, key=lambda z: z.priority_score, reverse=True)
    top_zone = high_p_zones[0] if high_p_zones else (zones[0] if zones else None)

    avg_lst = round(float(analyzed_df["lst_c"].mean()), 2) if "lst_c" in analyzed_df else None
    avg_ndvi = round(float(analyzed_df["ndvi"].mean()), 4) if "ndvi" in analyzed_df else None
    avg_built = round(float(analyzed_df["built_up"].mean()), 4) if "built_up" in analyzed_df else None
    priority_idx = round(float(analyzed_df["priority_score"].mean()), 4)

    return AnalyzeResponse(
        city=request.city,
        data_source=metadata.provider,
        synthetic_data=False,
        metadata=metadata,
        total_zones=len(zones),
        summary={k: int(counts.get(k, 0)) for k in ["Low", "Medium", "High"]},
        zones=zones,
        notice=metadata.notice,
        # Frontend compatibility fields
        avg_lst=avg_lst,
        avg_ndvi=avg_ndvi,
        high_priority_zones=int(counts.get("High", 0)),
        priority_index=priority_idx,
        built_up=avg_built,
        zone=top_zone,
        high_priority_zone_list=high_p_zones
    )

@app.get("/zones", tags=["Zones"])
def get_zones(
    category: Optional[str] = Query(default=None, pattern="^(Low|Medium|High)$"),
    limit: int = Query(default=100, ge=1, le=1000)
):
    """Returns filtered zones from the current active analysis."""
    df = _LATEST_ANALYSIS["df"]
    if df is None:
        df = run_analysis()
        _LATEST_ANALYSIS["df"] = df

    result = df.copy()
    if category:
        result = result[result["category"] == category]
    result = result.head(limit)

    return {
        "total_returned": len(result),
        "zones": [
            {
                "zone_id": str(r["zone_id"]),
                "lat": float(r["lat"]),
                "lon": float(r["lon"]),
                "priority_score": round(float(r["priority_score"]), 4),
                "category": str(r["category"]),
                "recommendations": r["recommendations"] if isinstance(r["recommendations"], list) else [r["recommendations"]],
                "indicators": {
                    k: round(float(r[k]), 4)
                    for k in ["heat", "ndvi", "built_up", "road_density", "green_area", "exposure"]
                    if k in r
                }
            }
            for _, r in result.iterrows()
        ]
    }

@app.get("/zones.geojson", tags=["Zones"])
def get_zones_geojson(
    geometry_type: str = Query(default="polygon", pattern="^(polygon|point)$"),
    category: Optional[str] = Query(default=None, pattern="^(Low|Medium|High)$")
):
    """
    Returns spatial GeoJSON features.
    Supports geometry_type='polygon' (grid boundaries) or 'point' (centroids).
    """
    df = _LATEST_ANALYSIS["df"]
    grid_cells = _LATEST_ANALYSIS["grid_cells"]
    
    if df is None:
        df = run_analysis()
        _LATEST_ANALYSIS["df"] = df

    filtered_df = df.copy()
    if category:
        filtered_df = filtered_df[filtered_df["category"] == category]

    return build_geojson(filtered_df, grid_cells=grid_cells, geometry_type=geometry_type)

@app.post("/what-if", response_model=WhatIfResponse, tags=["Scenarios"])
def what_if(request: WhatIfRequest):
    """
    Simulates changes to normalized environmental features (e.g. reducing heat, increasing NDVI)
    to calculate revised priority scores and updated green recommendations.
    """
    allowed = {"heat", "ndvi", "built_up", "road_density", "green_area", "exposure"}
    invalid = set(request.changes) - allowed
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported scenario features: {sorted(invalid)}. Allowed: {sorted(allowed)}"
        )
    if any(v < 0.0 or v > 1.0 for v in request.changes.values()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="All scenario change values must be normalized floats between 0.0 and 1.0."
        )

    df = _LATEST_ANALYSIS["df"]
    if df is None:
        df = run_analysis()
        _LATEST_ANALYSIS["df"] = df

    matches = df[df["zone_id"] == request.zone_id]
    if matches.empty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zone ID '{request.zone_id}' not found in active dataset."
        )

    row = matches.iloc[0].copy()
    baseline_score = float(row["priority_score"])
    baseline_category = str(row["category"])
    baseline_recs = row["recommendations"]
    if isinstance(baseline_recs, str):
        baseline_recs = [s.strip() for s in baseline_recs.split("|")]

    # Apply changes
    for key, value in request.changes.items():
        row[key] = value

    low_veg = (1.0 - float(row["ndvi"]))
    row["low_vegetation"] = low_veg
    
    # Recalculate score using weighted rule
    score = (
        WEIGHTS["heat"] * float(row["heat"]) +
        WEIGHTS["built_up"] * float(row["built_up"]) +
        WEIGHTS["road_density"] * float(row["road_density"]) +
        WEIGHTS["exposure"] * float(row["exposure"]) +
        WEIGHTS["low_vegetation"] * low_veg
    )
    score = max(0.0, min(1.0, score))
    category = "Low" if score < 0.33 else ("Medium" if score < 0.66 else "High")
    row["priority_score"] = score
    row["category"] = category

    scenario_details = generate_recommendation_details(row)
    scenario_recs = [d["action"] for d in scenario_details]

    return WhatIfResponse(
        zone_id=request.zone_id,
        baseline_score=round(baseline_score, 4),
        scenario_score=round(score, 4),
        score_change=round(score - baseline_score, 4),
        baseline_category=baseline_category,
        scenario_category=category,
        baseline_recommendations=baseline_recs,
        scenario_recommendations=scenario_recs,
        scenario_recommendation_details=[RecommendationDetail(**d) for d in scenario_details],
        notice="What-if simulation using weighted decision formula and updated environmental indicators."
    )

# Optional: Serve frontend static UI if present in project
frontend_dir = PROJECT_ROOT / "frontend"
if frontend_dir.exists():
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import RedirectResponse

    app.mount("/frontend", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

    @app.get("/ui", tags=["Frontend"])
    @app.get("/app", tags=["Frontend"])
    def open_ui():
        """Redirects to the interactive UrbanGreen AI frontend dashboard."""
        return RedirectResponse(url="/frontend/")
