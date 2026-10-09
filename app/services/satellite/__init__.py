import logging
from typing import Tuple, List
import pandas as pd
from .base import SatelliteDataProvider
from .gee_provider import GoogleEarthEngineProvider
from .open_geo_provider import OpenGeospatialProvider
from .dummy_provider import DummySatelliteProvider
from ..grid import GridCell
from ...schemas import DataSourceMetadata

logger = logging.getLogger(__name__)

gee_provider = GoogleEarthEngineProvider()
open_provider = OpenGeospatialProvider()
dummy_provider = DummySatelliteProvider()

def get_satellite_pipeline(force_synthetic: bool = False) -> SatelliteDataProvider:
    """
    Selects the best available satellite/geospatial data provider:
    1. If force_synthetic is True -> DummySatelliteProvider
    2. If Google Earth Engine is authenticated -> GoogleEarthEngineProvider
    3. Else -> OpenGeospatialProvider (Real public satellite temperature & OSM)
    """
    if force_synthetic:
        return dummy_provider

    # Check GEE credentials
    gee_ok, _ = gee_provider.is_available()
    if gee_ok:
        logger.info("Using Google Earth Engine provider for satellite acquisition.")
        return gee_provider

    # Fall back to real Open Geospatial / Satellite reanalysis
    logger.info("Using Open Geospatial & Satellite Reanalysis provider.")
    return open_provider

def acquire_environmental_data(
    city: str,
    bbox: Tuple[float, float, float, float],
    grid_cells: List[GridCell],
    force_synthetic: bool = False
) -> Tuple[pd.DataFrame, DataSourceMetadata]:
    """
    Acquires environmental data from the primary provider with automatic graceful fallback.
    """
    provider = get_satellite_pipeline(force_synthetic=force_synthetic)
    try:
        df, meta = provider.acquire_features(city, bbox, grid_cells)
        return df, meta
    except Exception as exc:
        logger.warning(f"Primary provider {provider.name} failed: {exc}. Falling back to synthetic demonstration data.")
        df, meta = dummy_provider.acquire_features(city, bbox, grid_cells)
        meta.warnings.append(f"Satellite acquisition error ({provider.name}): {str(exc)}. Reverted to synthetic fallback.")
        return df, meta
