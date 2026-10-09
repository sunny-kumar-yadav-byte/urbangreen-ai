from typing import List, Tuple
import pandas as pd
from .base import SatelliteDataProvider
from ..grid import GridCell
from ...schemas import DataSourceMetadata
from ...config import DATA_PATH

class DummySatelliteProvider(SatelliteDataProvider):
    """
    Provides reproducible synthetic demonstration data from dummy_zones.csv.
    """
    name = "synthetic_dummy"

    def is_available(self) -> Tuple[bool, str]:
        if DATA_PATH.exists():
            return True, "Synthetic demonstration dataset is available."
        return False, f"Dummy dataset not found at {DATA_PATH}"

    def acquire_features(
        self,
        city: str,
        bbox: Tuple[float, float, float, float],
        grid_cells: List[GridCell]
    ) -> Tuple[pd.DataFrame, DataSourceMetadata]:
        df = pd.read_csv(DATA_PATH)
        metadata = DataSourceMetadata(
            provider="synthetic_dummy",
            synthetic_data=True,
            satellite_source="Synthetic Grid Generator v0.2",
            acquisition_date="Synthetic Benchmark",
            resolution_meters=500,
            bounding_box=list(bbox),
            warnings=["Using synthetic demonstration data, not real satellite observations."],
            notice="Synthetic demonstration data only; not suitable for real-world planning."
        )
        return df, metadata
