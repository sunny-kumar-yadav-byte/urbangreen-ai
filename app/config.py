import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

DATA_PATH = DATA_DIR / "dummy_zones.csv"
RESULTS_PATH = DATA_DIR / "analysis_results.csv"

# Rule-based priority weights (must sum to ~1.0)
WEIGHTS = {
    "heat": float(os.getenv("WEIGHT_HEAT", "0.35")),
    "built_up": float(os.getenv("WEIGHT_BUILT_UP", "0.25")),
    "road_density": float(os.getenv("WEIGHT_ROAD_DENSITY", "0.15")),
    "exposure": float(os.getenv("WEIGHT_EXPOSURE", "0.15")),
    "low_vegetation": float(os.getenv("WEIGHT_LOW_VEGETATION", "0.10")),
}

# Google Earth Engine Configuration
EE_PROJECT_ID = os.getenv("EE_PROJECT_ID", "").strip() or None
EE_SERVICE_ACCOUNT = os.getenv("EE_SERVICE_ACCOUNT", "").strip() or None
EE_PRIVATE_KEY_FILE = os.getenv("EE_PRIVATE_KEY_FILE", "").strip() or None
EE_PRIVATE_KEY_JSON = os.getenv("EE_PRIVATE_KEY_JSON", "").strip() or None

# Geospatial & Remote Sensing settings
DEFAULT_GRID_SIZE_METERS = int(os.getenv("DEFAULT_GRID_SIZE_METERS", "500"))
MAX_GRID_CELLS = int(os.getenv("MAX_GRID_CELLS", "400"))
NOMINATIM_USER_AGENT = os.getenv("NOMINATIM_USER_AGENT", "UrbanGreenAI/0.3 (urban-greening-research; contact: info@urbangreen.local)")
OVERPASS_API_URL = os.getenv("OVERPASS_API_URL", "https://overpass-api.de/api/interpreter")
OPEN_METEO_API_URL = os.getenv("OPEN_METEO_API_URL", "https://archive-api.open-meteo.com/v1/archive")

# Reference bounds for absolute normalization across cities
# Allows meaningful priority comparison between different geographic regions
REFERENCE_BOUNDS = {
    "lst_c": (float(os.getenv("LST_MIN", "18.0")), float(os.getenv("LST_MAX", "48.0"))),
    "ndvi": (float(os.getenv("NDVI_MIN", "-0.1")), float(os.getenv("NDVI_MAX", "0.85"))),
    "built_up": (0.0, 1.0),
    "road_density": (0.0, 1.0),
    "green_area": (0.0, 1.0),
    "exposure": (0.0, 1.0),
}
