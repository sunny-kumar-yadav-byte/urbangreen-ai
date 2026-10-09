import math
from dataclasses import dataclass
from typing import List, Tuple
from shapely.geometry import Polygon, box
from ..config import DEFAULT_GRID_SIZE_METERS, MAX_GRID_CELLS

@dataclass
class GridCell:
    zone_id: str
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float
    centroid_lon: float
    centroid_lat: float
    polygon: Polygon
    polygon_coordinates: list[list[list[float]]]
    area_m2: float

def generate_spatial_grid(
    bbox: Tuple[float, float, float, float],
    target_grid_size_m: int = DEFAULT_GRID_SIZE_METERS,
    max_cells: int = MAX_GRID_CELLS
) -> List[GridCell]:
    """
    Subdivides a bounding box (min_lon, min_lat, max_lon, max_lat) into a regular
    spatial grid of polygon cells, capped at max_cells for performance.
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    center_lat = (min_lat + max_lat) / 2.0
    
    # Earth degree to meter approximations
    meters_per_deg_lat = 111320.0
    meters_per_deg_lon = max(111320.0 * math.cos(math.radians(center_lat)), 1000.0)
    
    total_width_m = (max_lon - min_lon) * meters_per_deg_lon
    total_height_m = (max_lat - min_lat) * meters_per_deg_lat
    
    # Calculate initial rows & cols
    cols = max(int(round(total_width_m / target_grid_size_m)), 1)
    rows = max(int(round(total_height_m / target_grid_size_m)), 1)
    
    # Adapt grid resolution if cell count exceeds max_cells
    if cols * rows > max_cells:
        scale_factor = math.sqrt((cols * rows) / max_cells)
        cols = max(int(cols / scale_factor), 1)
        rows = max(int(rows / scale_factor), 1)
        
    step_lon = (max_lon - min_lon) / cols
    step_lat = (max_lat - min_lat) / rows
    
    cells: List[GridCell] = []
    idx = 1
    
    for r in range(rows):
        c_min_lat = min_lat + r * step_lat
        c_max_lat = c_min_lat + step_lat
        for c in range(cols):
            c_min_lon = min_lon + c * step_lon
            c_max_lon = c_min_lon + step_lon
            
            centroid_lon = round((c_min_lon + c_max_lon) / 2.0, 6)
            centroid_lat = round((c_min_lat + c_max_lat) / 2.0, 6)
            
            poly = box(c_min_lon, c_min_lat, c_max_lon, c_max_lat)
            # GeoJSON polygon ring format: [[[lon, lat], ...]] (closed loop)
            coords = [[
                [round(c_min_lon, 6), round(c_min_lat, 6)],
                [round(c_max_lon, 6), round(c_min_lat, 6)],
                [round(c_max_lon, 6), round(c_max_lat, 6)],
                [round(c_min_lon, 6), round(c_max_lat, 6)],
                [round(c_min_lon, 6), round(c_min_lat, 6)]
            ]]
            
            cell_area = (step_lon * meters_per_deg_lon) * (step_lat * meters_per_deg_lat)
            
            cells.append(GridCell(
                zone_id=f"Z{idx:03d}",
                min_lon=round(c_min_lon, 6),
                min_lat=round(c_min_lat, 6),
                max_lon=round(c_max_lon, 6),
                max_lat=round(c_max_lat, 6),
                centroid_lon=centroid_lon,
                centroid_lat=centroid_lat,
                polygon=poly,
                polygon_coordinates=coords,
                area_m2=round(cell_area, 1)
            ))
            idx += 1
            
    return cells
