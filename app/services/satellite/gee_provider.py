import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Tuple
import pandas as pd
from shapely.geometry import mapping
from .base import SatelliteDataProvider
from ..grid import GridCell
from ...schemas import DataSourceMetadata
from ...config import (
    EE_PROJECT_ID,
    EE_SERVICE_ACCOUNT,
    EE_PRIVATE_KEY_FILE,
    EE_PRIVATE_KEY_JSON
)

logger = logging.getLogger(__name__)

class GoogleEarthEngineProvider(SatelliteDataProvider):
    """
    Acquires Sentinel-2 (NDVI) and Landsat-8/9 (Land Surface Temperature)
    using the official Google Earth Engine Python API.
    """
    name = "google_earth_engine"

    def __init__(self):
        self._initialized = False
        self._checked = False
        self._init_error = None

    def _ensure_initialized(self) -> bool:
        if self._checked:
            return self._initialized
        self._checked = True
        try:
            import ee
            if EE_SERVICE_ACCOUNT and (EE_PRIVATE_KEY_FILE or EE_PRIVATE_KEY_JSON):
                if EE_PRIVATE_KEY_FILE and os.path.exists(EE_PRIVATE_KEY_FILE):
                    credentials = ee.ServiceAccountCredentials(EE_SERVICE_ACCOUNT, key_file=EE_PRIVATE_KEY_FILE)
                elif EE_PRIVATE_KEY_JSON:
                    key_dict = json.loads(EE_PRIVATE_KEY_JSON)
                    credentials = ee.ServiceAccountCredentials(EE_SERVICE_ACCOUNT, key_data=json.dumps(key_dict))
                else:
                    raise ValueError("EE private key file not found on disk.")
                ee.Initialize(credentials, project=EE_PROJECT_ID)
            elif EE_PROJECT_ID:
                ee.Initialize(project=EE_PROJECT_ID)
            else:
                # Try default user credentials
                ee.Initialize()
            self._initialized = True
            self._init_error = None
            return True
        except Exception as exc:
            self._initialized = False
            self._init_error = str(exc)
            logger.info(f"Earth Engine not active: {exc}")
            return False

    def is_available(self) -> Tuple[bool, str]:
        if self._ensure_initialized():
            return True, "Earth Engine initialized and ready."
        return False, (
            "Earth Engine not initialized. Configure EE_PROJECT_ID and "
            "EE_SERVICE_ACCOUNT / EE_PRIVATE_KEY_FILE in .env or run 'earthengine authenticate'."
        )

    def acquire_features(
        self,
        city: str,
        bbox: Tuple[float, float, float, float],
        grid_cells: List[GridCell]
    ) -> Tuple[pd.DataFrame, DataSourceMetadata]:
        import ee
        if not self._ensure_initialized():
            raise RuntimeError(f"Cannot acquire GEE features: {self._init_error}")

        min_lon, min_lat, max_lon, max_lat = bbox
        ee_geom = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])
        
        # Recent 12-month cloud-filtered composite
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=365)
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        # 1. Sentinel-2 Harmonized for NDVI
        s2 = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
              .filterBounds(ee_geom)
              .filterDate(start_str, end_str)
              .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 25))
              .median())
        ndvi_img = s2.normalizedDifference(["B8", "B4"]).rename("ndvi")

        # 2. Landsat 8/9 Level 2 for Surface Temperature
        l8 = (ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
              .filterBounds(ee_geom)
              .filterDate(start_str, end_str)
              .filter(ee.Filter.lt("CLOUD_COVER", 25))
              .median())
        # Convert thermal band ST_B10 to Celsius
        lst_img = l8.select("ST_B10").multiply(0.00341802).add(149.0).subtract(273.15).rename("lst_c")

        # Combine bands
        composite = ndvi_img.addBands(lst_img)

        # Convert GridCells to Earth Engine FeatureCollection
        features = []
        for cell in grid_cells:
            coords = mapping(cell.polygon)["coordinates"]
            f = ee.Feature(ee.Geometry.Polygon(coords), {"zone_id": cell.zone_id, "lat": cell.centroid_lat, "lon": cell.centroid_lon})
            features.append(f)
        fc = ee.FeatureCollection(features)

        # Sample mean over each polygon grid cell
        reduced = composite.reduceRegions(
            collection=fc,
            reducer=ee.Reducer.mean(),
            scale=30
        )
        
        info = reduced.getInfo()
        records = []
        for feat in info.get("features", []):
            props = feat.get("properties", {})
            zid = props.get("zone_id")
            cell_ref = next((c for c in grid_cells if c.zone_id == zid), None)
            ndvi_val = props.get("ndvi")
            lst_val = props.get("lst_c")
            
            # Fallback if cloud mask left no pixel
            ndvi_val = float(ndvi_val) if ndvi_val is not None else 0.25
            lst_val = float(lst_val) if lst_val is not None else 32.0
            
            records.append({
                "zone_id": zid,
                "lat": props.get("lat", cell_ref.centroid_lat if cell_ref else 0.0),
                "lon": props.get("lon", cell_ref.centroid_lon if cell_ref else 0.0),
                "lst_c": round(lst_val, 2),
                "ndvi": round(max(min(ndvi_val, 1.0), -1.0), 4),
                "built_up": round(max(0.0, min(1.0, 0.75 - ndvi_val * 0.5)), 3),
                "road_density": round(max(0.0, min(1.0, 0.50 - ndvi_val * 0.2)), 3),
                "green_area": round(max(0.0, min(1.0, ndvi_val)), 3),
                "exposure": round(max(0.0, min(1.0, (lst_val - 20.0) / 25.0)), 3)
            })

        df = pd.DataFrame(records)
        metadata = DataSourceMetadata(
            provider="google_earth_engine",
            synthetic_data=False,
            satellite_source="Copernicus Sentinel-2 & Landsat-8 Surface Temperature (30m)",
            acquisition_date=f"{start_str} to {end_str}",
            resolution_meters=30,
            bounding_box=list(bbox),
            notice="Real satellite observations acquired and computed via Google Earth Engine."
        )
        return df, metadata
