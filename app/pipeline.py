import math
from typing import List, Dict, Any, Optional
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from .config import DATA_PATH, RESULTS_PATH, WEIGHTS, REFERENCE_BOUNDS
from .services.grid import GridCell

REQUIRED = {"zone_id", "lat", "lon", "ndvi", "lst_c", "built_up", "road_density", "green_area", "exposure"}
FEATURES = ["lst_c", "ndvi", "built_up", "road_density", "green_area", "exposure"]

def load_zones(path=DATA_PATH) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = REQUIRED - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    if df.empty:
        raise ValueError("Dataset is empty")
    if df["zone_id"].duplicated().any():
        raise ValueError("zone_id values must be unique")
    if df[FEATURES].isna().any().any():
        raise ValueError("Feature columns contain missing values")
    return df

def validate_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Validates an in-memory DataFrame against required schema."""
    missing = REQUIRED - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    if df.empty:
        raise ValueError("Dataset is empty")
    if df["zone_id"].duplicated().any():
        raise ValueError("zone_id values must be unique")
    if df[FEATURES].isna().any().any():
        raise ValueError("Feature columns contain missing values")
    return df

def normalize_features(df: pd.DataFrame, method: str = "reference") -> pd.DataFrame:
    """
    Normalizes environmental features into [0, 1] range.
    - 'reference': Uses absolute geographic reference bounds across all cities (recommended for cross-city consistency).
    - 'dataset_relative': Uses MinMaxScaler across only the passed dataset.
    """
    result = df.copy()
    if method == "dataset_relative":
        result[FEATURES] = MinMaxScaler().fit_transform(result[FEATURES])
        # LST mapped directly to heat
        result["heat"] = result["lst_c"]
        result["low_vegetation"] = (1.0 - result["ndvi"]).clip(0.0, 1.0)
    else:
        # Reference-based scaling
        lst_min, lst_max = REFERENCE_BOUNDS["lst_c"]
        ndvi_min, ndvi_max = REFERENCE_BOUNDS["ndvi"]
        
        # Scale heat from land-surface temp
        result["heat"] = ((result["lst_c"] - lst_min) / (lst_max - lst_min)).clip(0.0, 1.0)
        # Scaled NDVI for vegetation scoring
        scaled_ndvi = ((result["ndvi"] - ndvi_min) / (ndvi_max - ndvi_min)).clip(0.0, 1.0)
        result["low_vegetation"] = (1.0 - scaled_ndvi).clip(0.0, 1.0)
        
        # Built-up, road_density, green_area, exposure are already in [0, 1] ratios
        for col in ["built_up", "road_density", "green_area", "exposure"]:
            result[col] = result[col].clip(0.0, 1.0)

    return result

def calculate_priority(df: pd.DataFrame) -> pd.DataFrame:
    """
    Applies the rule-based weighted prioritization formula to calculate priority_score and category.
    """
    result = df.copy()
    if "heat" not in result.columns:
        result["heat"] = result["lst_c"]
    if "low_vegetation" not in result.columns:
        result["low_vegetation"] = (1.0 - result["ndvi"]).clip(0.0, 1.0)
        
    result["priority_score"] = (
        WEIGHTS["heat"] * result["heat"] +
        WEIGHTS["built_up"] * result["built_up"] +
        WEIGHTS["road_density"] * result["road_density"] +
        WEIGHTS["exposure"] * result["exposure"] +
        WEIGHTS["low_vegetation"] * result["low_vegetation"]
    ).clip(0.0, 1.0)
    
    result["category"] = result["priority_score"].apply(
        lambda s: "Low" if s < 0.33 else ("Medium" if s < 0.66 else "High")
    )
    return result

def generate_recommendation_details(row: pd.Series) -> List[Dict[str, str]]:
    """
    Generates structured, validated rule-based intervention recommendations with urgency tiers.
    """
    details: List[Dict[str, str]] = []
    
    heat = float(row.get("heat", row.get("lst_c", 0.0)))
    ndvi = float(row.get("ndvi", 0.0))
    built_up = float(row.get("built_up", 0.0))
    road_density = float(row.get("road_density", 0.0))
    green_area = float(row.get("green_area", 0.0))
    exposure = float(row.get("exposure", 0.0))

    # 1. Critical Tree Canopy: Extreme Heat + Low Vegetation
    if heat >= 0.65 and ndvi <= 0.35:
        details.append({
            "action": "Assess suitable locations for tree canopy",
            "category": "Canopy Expansion",
            "urgency": "Critical",
            "rationale": "High surface heat combined with sparse vegetation canopy causes localized urban heat island."
        })
    # 2. Cool Roofs: Extreme Heat + High Built-up
    if heat >= 0.65 and built_up >= 0.70:
        details.append({
            "action": "Evaluate cool roofs and reflective surfaces",
            "category": "Cool Surface",
            "urgency": "High",
            "rationale": "Dense impervious built structures absorb and re-radiate thermal energy."
        })
    # 3. Shaded Mobility Corridors: High Road Density + Low Vegetation
    if road_density >= 0.60 and ndvi <= 0.35:
        details.append({
            "action": "Assess shaded pedestrian and mobility corridors",
            "category": "Mobility Corridor",
            "urgency": "High",
            "rationale": "Dense road networks lacking tree canopy subject pedestrians to severe thermal stress."
        })
    # 4. Pocket Parks / Micro-Forests: Low Green Area (< 0.20)
    if green_area <= 0.20:
        details.append({
            "action": "Identify feasible sites for new or expanded green space",
            "category": "Green Space Creation",
            "urgency": "Critical" if exposure >= 0.60 else "High",
            "rationale": "Vegetated surface area is below recommended neighborhood environmental thresholds."
        })
    # 5. Permeable Pavements & Bioswales: High Built-up + High Road Density
    if built_up >= 0.65 and road_density >= 0.55:
        details.append({
            "action": "Implement permeable pavements and roadside bioswales",
            "category": "Stormwater & Permeability",
            "urgency": "Medium",
            "rationale": "High impervious footprint limits stormwater infiltration and amplifies surface runoff."
        })
    # 6. Default stewardship recommendation
    if not details:
        details.append({
            "action": "Maintain existing green cover and monitor conditions",
            "category": "Stewardship",
            "urgency": "Maintenance",
            "rationale": "Vegetation index and thermal metrics meet baseline urban environmental targets."
        })
        
    return details

def generate_recommendations(row: pd.Series) -> List[str]:
    """Returns flat list of recommendation action strings for backwards compatibility."""
    return [item["action"] for item in generate_recommendation_details(row)]

def run_analysis(
    data: Optional[pd.DataFrame] = None,
    path=DATA_PATH,
    normalization_method: str = "dataset_relative"
) -> pd.DataFrame:
    """
    Main analysis pipeline:
    Accepts an existing DataFrame or loads from CSV path.
    """
    if data is not None:
        raw = validate_dataframe(data)
    else:
        raw = load_zones(path)
        
    normalized = normalize_features(raw, method=normalization_method)
    result = calculate_priority(normalized)
    result["recommendation_details"] = result.apply(generate_recommendation_details, axis=1)
    result["recommendations"] = result["recommendation_details"].apply(lambda items: [i["action"] for i in items])
    return result

def save_results(df: pd.DataFrame, path=RESULTS_PATH):
    out = df.copy()
    if "recommendation_details" in out.columns:
        out = out.drop(columns=["recommendation_details"])
    if "recommendations" in out.columns and isinstance(out["recommendations"].iloc[0], list):
        out["recommendations"] = out["recommendations"].apply(lambda values: " | ".join(values))
    out.to_csv(path, index=False)

def build_geojson(
    df: pd.DataFrame,
    grid_cells: Optional[List[GridCell]] = None,
    geometry_type: str = "Polygon"
) -> Dict[str, Any]:
    """
    Builds a standard GeoJSON FeatureCollection.
    If grid_cells or polygon_coordinates are provided, outputs 'Polygon' geometries.
    Otherwise falls back to 'Point' geometry.
    """
    # Create lookup map for polygon geometries if grid_cells provided
    cell_polygon_map = {c.zone_id: c.polygon_coordinates for c in grid_cells} if grid_cells else {}

    features = []
    for _, r in df.iterrows():
        zid = str(r["zone_id"])
        lat = float(r["lat"])
        lon = float(r["lon"])
        
        polygon_coords = cell_polygon_map.get(zid)
        if polygon_coords is None and "polygon_coordinates" in r and r["polygon_coordinates"] is not None:
            polygon_coords = r["polygon_coordinates"]

        if geometry_type.lower() == "polygon" and polygon_coords is not None:
            geom = {
                "type": "Polygon",
                "coordinates": polygon_coords
            }
        else:
            geom = {
                "type": "Point",
                "coordinates": [lon, lat]
            }

        recs = r["recommendations"]
        if isinstance(recs, str):
            recs = [s.strip() for s in recs.split("|")]

        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "zone_id": zid,
                "priority_score": round(float(r["priority_score"]), 4),
                "category": str(r["category"]),
                "recommendations": recs,
                "heat": round(float(r["heat"]), 4) if "heat" in r else round(float(r.get("lst_c", 0)), 4),
                "ndvi": round(float(r["ndvi"]), 4),
                "built_up": round(float(r["built_up"]), 4),
                "road_density": round(float(r["road_density"]), 4),
                "green_area": round(float(r["green_area"]), 4),
                "exposure": round(float(r["exposure"]), 4),
                "lst_c": round(float(r["lst_c"]), 2) if "lst_c" in r else None
            }
        })

    return {"type": "FeatureCollection", "features": features}
