from abc import ABC, abstractmethod
from typing import List, Tuple
import pandas as pd
from ..grid import GridCell
from ...schemas import DataSourceMetadata

class SatelliteDataProvider(ABC):
    """
    Abstract base class for satellite data acquisition and geospatial indicator extraction.
    """
    name: str

    @abstractmethod
    def is_available(self) -> Tuple[bool, str]:
        """
        Returns (True, "Ready") or (False, "Reason why unavailable / credentials missing").
        """
        pass

    @abstractmethod
    def acquire_features(
        self,
        city: str,
        bbox: Tuple[float, float, float, float],
        grid_cells: List[GridCell]
    ) -> Tuple[pd.DataFrame, DataSourceMetadata]:
        """
        Acquires or extracts environmental features for the grid cells.
        Returns a DataFrame containing:
          ['zone_id', 'lat', 'lon', 'lst_c', 'ndvi', 'built_up', 'road_density', 'green_area', 'exposure']
        plus metadata describing the genuine source.
        """
        pass
