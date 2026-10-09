import logging
from typing import Tuple
import httpx
from ..config import NOMINATIM_USER_AGENT

logger = logging.getLogger(__name__)

# Fallback bounding boxes for major benchmark cities [min_lon, min_lat, max_lon, max_lat]
KNOWN_CITY_BOUNDS: dict[str, Tuple[float, float, float, float]] = {
    "bhopal": (77.3400, 23.1800, 77.5200, 23.3200),
    "delhi": (77.0000, 28.5000, 77.3500, 28.7500),
    "mumbai": (72.7800, 18.9000, 72.9800, 19.2500),
    "bengaluru": (77.4800, 12.8500, 77.7200, 13.0800),
    "bangalore": (77.4800, 12.8500, 77.7200, 13.0800),
    "new york": (-74.0500, 40.6800, -73.8500, 40.8500),
    "london": (-0.2500, 51.4200, 0.0500, 51.5800),
    "paris": (2.2500, 48.8100, 2.4200, 48.9100),
}

def geocode_city_bbox(city: str, timeout: float = 6.0) -> Tuple[float, float, float, float]:
    """
    Geocodes a city name to a bounding box: (min_lon, min_lat, max_lon, max_lat).
    Uses OpenStreetMap Nominatim with timeout and fallbacks.
    """
    clean_city = city.strip().lower()
    
    # 1. Check known city bounds cache
    if clean_city in KNOWN_CITY_BOUNDS:
        return KNOWN_CITY_BOUNDS[clean_city]
    
    # 2. Query Nominatim API
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": city,
        "format": "json",
        "polygon_geojson": 0,
        "limit": 1
    }
    headers = {"User-Agent": NOMINATIM_USER_AGENT}
    
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url, params=params, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if data and len(data) > 0:
                    # boundingbox is [lat_min, lat_max, lon_min, lon_max] in Nominatim
                    bbox = data[0].get("boundingbox")
                    if bbox and len(bbox) == 4:
                        lat_min, lat_max, lon_min, lon_max = (
                            float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
                        )
                        return (lon_min, lat_min, lon_max, lat_max)
    except Exception as exc:
        logger.warning(f"Nominatim geocoding failed for '{city}': {exc}. Using fallback bounding box.")
    
    # 3. Default fallback if city not resolved
    # Use Bhopal coordinates as reference prototype boundary
    return KNOWN_CITY_BOUNDS["bhopal"]
