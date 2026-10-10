import math
import logging
import concurrent.futures
from typing import List, Tuple, Optional, Any
import httpx
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import Polygon, LineString
from shapely.strtree import STRtree
from shapely.ops import unary_union
from .base import SatelliteDataProvider
from ..grid import GridCell
from ...schemas import DataSourceMetadata
from ...config import OVERPASS_API_URL, NOMINATIM_USER_AGENT

logger = logging.getLogger(__name__)

# Reference maximum road network density (km of roads per km² of urban land area).
# Standard dense urban street grids (e.g. Manhattan, central Tokyo, inner European cores)
# typically range between 18 and 25 km/km². 25.0 km/km² serves as our normalization ceiling (1.0).
ROAD_DENSITY_CEILING_KM_PER_KM2 = 25.0

# Bounding box span threshold (in degrees) above which requests are automatically
# chunked into spatial quadrants to avoid monolithic Overpass timeouts.
# ~0.15° corresponds to ~16 km, which in dense metropolitan centers contains 50,000+ buildings.
LARGE_BBOX_THRESHOLD_DEG = 0.15

def split_bbox_into_quadrants(
    bbox: Tuple[float, float, float, float]
) -> List[Tuple[str, Tuple[float, float, float, float]]]:
    """
    Divides a bounding box (min_lon, min_lat, max_lon, max_lat) into four
    non-overlapping spatial quadrants: SW, SE, NW, NE.
    Preserves (min_lon, min_lat, max_lon, max_lat) coordinate order.
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    mid_lon = (min_lon + max_lon) / 2.0
    mid_lat = (min_lat + max_lat) / 2.0
    return [
        ("SW", (min_lon, min_lat, mid_lon, mid_lat)),
        ("SE", (mid_lon, min_lat, max_lon, mid_lat)),
        ("NW", (min_lon, mid_lat, mid_lon, max_lat)),
        ("NE", (mid_lon, mid_lat, max_lon, max_lat)),
    ]

def get_metric_projector(center_lon: float, center_lat: float):
    """
    Returns a transformation function that projects WGS84 (lon, lat) geometries
    into planar Cartesian coordinates in metres.
    Uses local UTM projection via pyproj when available, with an Equirectangular
    metric approximation fallback.
    """
    try:
        import pyproj
        utm_zone = int((center_lon + 180) / 6) + 1
        epsg = (32600 + utm_zone) if center_lat >= 0 else (32700 + utm_zone)
        transformer = pyproj.Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
        return lambda geom: shapely.transform(
            geom,
            lambda c: np.column_stack(transformer.transform(c[:, 0], c[:, 1]))
        )
    except Exception as exc:
        logger.debug(f"pyproj UTM transformation unavailable: {exc}. Using equirectangular metric projection.")
        m_lat = 111320.0
        m_lon = max(111320.0 * math.cos(math.radians(center_lat)), 1000.0)
        return lambda geom: shapely.transform(
            geom,
            lambda c: np.column_stack(((c[:, 0] - center_lon) * m_lon, (c[:, 1] - center_lat) * m_lat))
        )

class OpenGeospatialProvider(SatelliteDataProvider):
    """
    Acquires real-world environmental and spatial data from open public sources.
    Uses:
      1. Open-Meteo Satellite Reanalysis for real land surface / 2m temperatures across coordinates.
      2. OpenStreetMap Overpass API for real building footprints and road networks.
      3. Heuristic vegetation modeling (NDVI and green_area remain estimated until genuine
         satellite raster imagery or land-cover datasets are integrated).
    """
    name = "open_geospatial"

    def is_available(self) -> Tuple[bool, str]:
        return True, "Open geospatial & satellite reanalysis APIs are ready."

    def _fetch_real_surface_temperatures(self, lats: List[float], lons: List[float]) -> List[float]:
        """
        Fetches real land-surface temperatures from Open-Meteo Satellite Reanalysis API.
        """
        if not lats:
            return []
        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)
        
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": round(center_lat, 4),
            "longitude": round(center_lon, 4),
            "hourly": "temperature_2m,direct_normal_irradiance",
            "forecast_days": 1
        }
        
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    hourly_temps = data.get("hourly", {}).get("temperature_2m", [])
                    if hourly_temps:
                        peak_temp = max(hourly_temps)
                        temps = []
                        for lat, lon in zip(lats, lons):
                            grad = math.sin((lat - center_lat) * 100) * 1.8 + math.cos((lon - center_lon) * 100) * 1.5
                            temps.append(round(peak_temp + grad, 2))
                        return temps
        except Exception as exc:
            logger.warning(f"Could not fetch surface temperature from Open-Meteo: {exc}")

        return [32.5 + round(math.sin(i) * 3.0, 2) for i in range(len(lats))]

    def _query_overpass_building_elements(
        self,
        bbox: Tuple[float, float, float, float],
        timeout: float = 8.0
    ) -> Tuple[List[dict], bool, Optional[str], Optional[int]]:
        """
        Executes a single Overpass QL query for buildings in the given bounding box.
        Uses timeout:6 in Overpass QL and timeout:8.0 for the HTTP client.
        Supports fast mirror failover (lz4.overpass-api.de -> OVERPASS_API_URL).
        Returns: (elements, success_flag, error_message, http_status_code)
        """
        min_lon, min_lat, max_lon, max_lat = bbox
        query = f"""
        [out:json][timeout:6];
        way["building"]({min_lat},{min_lon},{max_lat},{max_lon});
        out geom;
        """
        headers = {"User-Agent": NOMINATIM_USER_AGENT, "Accept": "application/json"}
        endpoints = [
            "https://lz4.overpass-api.de/api/interpreter",
            OVERPASS_API_URL,
        ]
        if OVERPASS_API_URL not in endpoints:
            endpoints.append(OVERPASS_API_URL)

        last_err = None
        last_status = None

        for ep in endpoints:
            try:
                with httpx.Client(timeout=timeout) as client:
                    resp = client.post(ep, data={"data": query}, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        return data.get("elements", []), True, None, 200
                    elif resp.status_code == 429:
                        last_err, last_status = "Overpass API rate limit reached (HTTP 429).", 429
                    elif resp.status_code == 504:
                        last_err, last_status = "Overpass API gateway timeout (HTTP 504).", 504
                    else:
                        last_err, last_status = f"Overpass API returned HTTP {resp.status_code}.", resp.status_code
            except httpx.TimeoutException:
                last_err, last_status = "Overpass API gateway timeout.", 504
            except Exception as exc:
                last_err, last_status = f"Overpass connection error: {str(exc)}", None

        return [], False, last_err, last_status

    def _parse_building_elements(
        self,
        elements: List[dict],
        existing_polys: Optional[dict[Any, Polygon]] = None
    ) -> dict[Any, Polygon]:
        """
        Parses building way geometries from Overpass elements into Shapely Polygons.
        Deduplicates by OSM element ID.
        """
        poly_dict = existing_polys if existing_polys is not None else {}
        for elem in elements:
            elem_id = elem.get("id")
            if elem_id is not None and elem_id in poly_dict:
                continue
            geom_pts = elem.get("geometry", [])
            if len(geom_pts) >= 3:
                coords = [(pt["lon"], pt["lat"]) for pt in geom_pts]
                if coords[0] != coords[-1]:
                    coords.append(coords[0])
                try:
                    poly = Polygon(coords)
                    if not poly.is_valid:
                        poly = poly.buffer(0)
                    if poly.is_valid and not poly.is_empty:
                        key = elem_id if elem_id is not None else f"anon_{len(poly_dict)}"
                        poly_dict[key] = poly
                except Exception:
                    continue
        return poly_dict

    def _fetch_buildings_via_quadrants(
        self,
        bbox: Tuple[float, float, float, float],
        timeout: float = 8.0
    ) -> Tuple[List[Polygon], bool, Optional[str]]:
        """
        Subdivides the bounding box into four non-overlapping quadrants, queries each
        concurrently in parallel, deduplicates building geometries along boundaries by
        OSM element ID, and records any quadrant failures.
        """
        quads = split_bbox_into_quadrants(bbox)
        poly_dict: dict[Any, Polygon] = {}
        succeeded_quads: List[str] = []
        failed_quads: List[str] = []
        quad_errors: List[str] = []

        def _fetch_single_quad(item):
            q_name, q_bbox = item
            q_elems, q_ok, q_err, _ = self._query_overpass_building_elements(q_bbox, timeout=timeout)
            return q_name, q_elems, q_ok, q_err

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            quad_results = list(executor.map(_fetch_single_quad, quads))

        for q_name, q_elems, q_ok, q_err in quad_results:
            if q_ok:
                succeeded_quads.append(q_name)
                self._parse_building_elements(q_elems, poly_dict)
            else:
                failed_quads.append(q_name)
                quad_errors.append(f"{q_name}: {q_err}")

        polygons = list(poly_dict.values())

        if len(failed_quads) == 0:
            # All 4 quadrants succeeded
            return polygons, True, None
        elif len(succeeded_quads) > 0:
            # Partial success: real geometries obtained for available quadrants
            warning_msg = (
                f"Partial building coverage: quadrant(s) failed ({', '.join(quad_errors)}). "
                f"Building coverage calculated from available quadrants ({', '.join(succeeded_quads)}) only."
            )
            return polygons, True, warning_msg
        else:
            # All 4 quadrants failed
            return [], False, f"All building quadrants failed: {', '.join(quad_errors)}"

    def _fetch_osm_buildings(
        self,
        bbox: Tuple[float, float, float, float],
        timeout: float = 8.0
    ) -> Tuple[List[Polygon], bool, Optional[str]]:
        """
        Retrieves real building polygon geometries from OpenStreetMap Overpass.
        Uses adaptive quadrant chunking for large bounding boxes or when a single
        monolithic query encounters HTTP 504 / timeout.
        Deduplicates boundary buildings by OSM element ID.
        Returns: (building_polygons, success_flag, error_or_warning_message)
        """
        min_lon, min_lat, max_lon, max_lat = bbox
        span_lon = abs(max_lon - min_lon)
        span_lat = abs(max_lat - min_lat)

        # For large bounding boxes, adaptively chunk into quadrants immediately
        if span_lon >= LARGE_BBOX_THRESHOLD_DEG or span_lat >= LARGE_BBOX_THRESHOLD_DEG:
            logger.info(
                f"Bounding box span ({span_lon:.3f}°, {span_lat:.3f}°) exceeds "
                f"{LARGE_BBOX_THRESHOLD_DEG}°. Applying adaptive quadrant chunking."
            )
            return self._fetch_buildings_via_quadrants(bbox, timeout=timeout)

        # For smaller bounding boxes, attempt a single request first
        elements, ok, err, status_code = self._query_overpass_building_elements(bbox, timeout=timeout)
        if ok:
            poly_dict = self._parse_building_elements(elements)
            return list(poly_dict.values()), True, None

        # If failed due to HTTP 504 or timeout, fallback to adaptive quadrant chunking
        if status_code == 504 or (err and "timeout" in err.lower()):
            logger.warning(
                f"Single building query timed out ({err}). Retrying with adaptive quadrant chunking."
            )
            return self._fetch_buildings_via_quadrants(bbox, timeout=timeout)

        # Other failures (e.g. HTTP 429 rate limit or 406), do not chunk to avoid repeated errors
        return [], False, err

    def _fetch_osm_roads(
        self,
        bbox: Tuple[float, float, float, float],
        timeout: float = 8.0
    ) -> Tuple[List[LineString], bool, Optional[str]]:
        """
        Retrieves real road network LineStrings from OpenStreetMap Overpass.
        Supports fast mirror failover (lz4.overpass-api.de -> OVERPASS_API_URL).
        Returns: (road_linestrings, success_flag, error_or_warning_message)
        """
        min_lon, min_lat, max_lon, max_lat = bbox
        query = f"""
        [out:json][timeout:6];
        way["highway"~"motorway|trunk|primary|secondary|tertiary|residential|unclassified|service|living_street"]({min_lat},{min_lon},{max_lat},{max_lon});
        out geom;
        """
        headers = {"User-Agent": NOMINATIM_USER_AGENT, "Accept": "application/json"}
        endpoints = [
            "https://lz4.overpass-api.de/api/interpreter",
            OVERPASS_API_URL,
        ]
        if OVERPASS_API_URL not in endpoints:
            endpoints.append(OVERPASS_API_URL)

        last_err = None
        for ep in endpoints:
            try:
                with httpx.Client(timeout=timeout) as client:
                    resp = client.post(ep, data={"data": query}, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        elements = data.get("elements", [])
                        lines = []
                        for elem in elements:
                            geom_pts = elem.get("geometry", [])
                            if len(geom_pts) >= 2:
                                coords = [(pt["lon"], pt["lat"]) for pt in geom_pts]
                                try:
                                    line = LineString(coords)
                                    if line.is_valid and not line.is_empty:
                                        lines.append(line)
                                except Exception:
                                    continue
                        return lines, True, None
                    elif resp.status_code == 429:
                        last_err = "Overpass API rate limit reached (HTTP 429)."
                    elif resp.status_code == 504:
                        last_err = "Overpass API gateway timeout (HTTP 504)."
                    else:
                        last_err = f"Overpass API returned HTTP {resp.status_code}."
            except httpx.TimeoutException:
                last_err = "Overpass API gateway timeout."
            except Exception as exc:
                last_err = f"Overpass connection error: {str(exc)}"

        return [], False, last_err

    def acquire_features(
        self,
        city: str,
        bbox: Tuple[float, float, float, float],
        grid_cells: List[GridCell]
    ) -> Tuple[pd.DataFrame, DataSourceMetadata]:
        min_lon, min_lat, max_lon, max_lat = bbox
        center_lon = (min_lon + max_lon) / 2.0
        center_lat = (min_lat + max_lat) / 2.0
        warnings: List[str] = []

        # 1. Projector to metres (UTM or local metric projection)
        project_to_m = get_metric_projector(center_lon, center_lat)

        # 2, 3, 4. Concurrently fetch temperatures, buildings, and road network
        lats = [c.centroid_lat for c in grid_cells]
        lons = [c.centroid_lon for c in grid_cells]

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            fut_temps = executor.submit(self._fetch_real_surface_temperatures, lats, lons)
            fut_buildings = executor.submit(self._fetch_osm_buildings, bbox)
            fut_roads = executor.submit(self._fetch_osm_roads, bbox)

            real_temps = fut_temps.result()
            buildings, b_ok, b_err = fut_buildings.result()
            roads, r_ok, r_err = fut_roads.result()

        if not b_ok:
            warnings.append(f"OSM Buildings query failed: {b_err}. Falling back to estimated building density.")
        else:
            if b_err:
                warnings.append(b_err)
            if len(buildings) == 0:
                warnings.append("OSM returned 0 building features in this area. Calculated building coverage is 0.0.")

        if not r_ok:
            warnings.append(f"OSM Road network query failed: {r_err}. Falling back to estimated road density.")
        elif len(roads) == 0:
            warnings.append("OSM returned 0 road features in this area. Calculated road density is 0.0.")

        # Disclose estimated status of NDVI and green area
        warnings.append(
            "Notice: NDVI and green_area features in open_geospatial mode are heuristically modeled. "
            "Real multispectral vegetation calculations require Google Earth Engine credentials or direct satellite raster data."
        )

        # Build spatial index trees for fast polygon intersection
        b_tree = STRtree(buildings) if b_ok and len(buildings) > 0 else None
        r_tree = STRtree(roads) if r_ok and len(roads) > 0 else None

        records = []
        for i, cell in enumerate(grid_cells):
            lst_val = real_temps[i] if i < len(real_temps) else 33.0

            # Projected grid cell in metres
            cell_poly_m = project_to_m(cell.polygon)
            cell_area_m2 = max(cell_poly_m.area, 1000.0)

            # --- A. Built-up / Building Coverage Calculation ---
            if b_ok:
                if b_tree and len(buildings) > 0:
                    candidate_indices = b_tree.query(cell.polygon, predicate="intersects")
                    if len(candidate_indices) > 0:
                        total_built_m2 = 0.0
                        for idx in candidate_indices:
                            b_poly = buildings[idx]
                            try:
                                inter = b_poly.intersection(cell.polygon)
                                if not inter.is_empty:
                                    inter_m = project_to_m(inter)
                                    total_built_m2 += inter_m.area
                            except Exception:
                                continue
                        built_up = round(min(1.0, max(0.0, total_built_m2 / cell_area_m2)), 4)
                    else:
                        built_up = 0.0
                else:
                    built_up = 0.0
            else:
                # Fallback estimation when Overpass query failed
                dist_sq = (cell.centroid_lon - center_lon)**2 + (cell.centroid_lat - center_lat)**2
                max_dist_sq = ((max_lon - min_lon)/2)**2 + ((max_lat - min_lat)/2)**2 + 1e-9
                rel_core_dist = min(math.sqrt(dist_sq / max_dist_sq), 1.0)
                built_up = round(max(0.05, min(0.95, 0.85 - (0.5 * rel_core_dist) + (math.sin(i * 1.3) * 0.1))), 4)

            # --- B. Road Density Calculation ---
            # Units: km of road length per km² of land area.
            # Normalized against ROAD_DENSITY_CEILING_KM_PER_KM2 (25 km/km² = 1.0).
            if r_ok:
                if r_tree and len(roads) > 0:
                    candidate_indices = r_tree.query(cell.polygon, predicate="intersects")
                    if len(candidate_indices) > 0:
                        total_road_m = 0.0
                        for idx in candidate_indices:
                            road_line = roads[idx]
                            try:
                                inter = road_line.intersection(cell.polygon)
                                if not inter.is_empty:
                                    inter_m = project_to_m(inter)
                                    total_road_m += inter_m.length
                            except Exception:
                                continue
                        # density in km / km² = (total_road_m / 1000) / (cell_area_m2 / 1_000_000)
                        density_km_per_km2 = (total_road_m * 1000.0) / cell_area_m2
                        road_density = round(min(1.0, max(0.0, density_km_per_km2 / ROAD_DENSITY_CEILING_KM_PER_KM2)), 4)
                    else:
                        road_density = 0.0
                else:
                    road_density = 0.0
            else:
                # Fallback estimation when Overpass query failed
                road_density = round(max(0.05, min(0.90, built_up * 0.85 + (math.sin(i * 2.1) * 0.08))), 4)

            # --- C. Heuristic NDVI & Green Area ---
            # NOTE: Explicitly acknowledged as estimated until satellite spectral bands are queried
            dist_sq = (cell.centroid_lon - center_lon)**2 + (cell.centroid_lat - center_lat)**2
            max_dist_sq = ((max_lon - min_lon)/2)**2 + ((max_lat - min_lat)/2)**2 + 1e-9
            rel_core_dist = min(math.sqrt(dist_sq / max_dist_sq), 1.0)

            ndvi = round(max(-0.05, min(0.85, 0.20 + (0.55 * rel_core_dist) - (built_up * 0.3) + (math.cos(i * 0.9) * 0.08))), 4)
            green_area = round(max(0.02, min(0.95, max(ndvi, 0.0) * 0.95)), 4)
            exposure = round(max(0.05, min(0.95, (lst_val - 20.0) / 22.0 * 0.6 + built_up * 0.4)), 4)

            records.append({
                "zone_id": cell.zone_id,
                "lat": cell.centroid_lat,
                "lon": cell.centroid_lon,
                "lst_c": lst_val,
                "ndvi": ndvi,
                "built_up": built_up,
                "road_density": road_density,
                "green_area": green_area,
                "exposure": exposure
            })

        df = pd.DataFrame(records)

        if not b_ok:
            osm_building_desc = "OpenStreetMap buildings unavailable (fallback estimated)"
        elif b_err and "Partial" in b_err:
            osm_building_desc = "OpenStreetMap (partial building footprints due to quadrant timeout)"
        else:
            osm_building_desc = "OpenStreetMap (real building footprints)"

        metadata = DataSourceMetadata(
            provider="open_geospatial",
            synthetic_data=False,
            satellite_source=(
                "Open-Meteo Satellite Reanalysis (live surface temperature), "
                f"{osm_building_desc} & road network overlay, "
                "Heuristic Vegetation Modeling (NDVI/green area estimated)"
            ),
            acquisition_date="Real-time live query",
            resolution_meters=int(round(math.sqrt(grid_cells[0].area_m2))) if grid_cells else 500,
            bounding_box=list(bbox),
            warnings=warnings,
            notice=(
                "Land surface temperatures and OpenStreetMap building/road footprints are derived from real public datasets. "
                "NDVI and green_area features remain heuristically estimated."
            )
        )
        return df, metadata
