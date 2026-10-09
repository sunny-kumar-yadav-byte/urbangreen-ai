import pytest
import pandas as pd
from shapely.geometry import Polygon, LineString, box
from app.services.grid import generate_spatial_grid
from app.services.geocoding import geocode_city_bbox, KNOWN_CITY_BOUNDS
from app.services.satellite import (
    acquire_environmental_data,
    gee_provider,
    open_provider,
    dummy_provider
)
from app.services.satellite.open_geo_provider import OpenGeospatialProvider, ROAD_DENSITY_CEILING_KM_PER_KM2
from app.services.satellite.base import SatelliteDataProvider
from app.pipeline import normalize_features, calculate_priority, validate_dataframe

def test_spatial_grid_generation():
    # Bhopal bbox
    bbox = (77.35, 23.20, 77.45, 23.30)
    cells = generate_spatial_grid(bbox, target_grid_size_m=1000, max_cells=50)
    
    assert len(cells) > 0
    assert len(cells) <= 50
    for cell in cells:
        assert cell.zone_id.startswith("Z")
        assert bbox[0] <= cell.centroid_lon <= bbox[2]
        assert bbox[1] <= cell.centroid_lat <= bbox[3]
        assert len(cell.polygon_coordinates[0]) == 5
        # Verify closed polygon ring
        assert cell.polygon_coordinates[0][0] == cell.polygon_coordinates[0][-1]

def test_geocoding_known_and_fallback():
    bhopal_bbox = geocode_city_bbox("Bhopal")
    assert bhopal_bbox == KNOWN_CITY_BOUNDS["bhopal"]

    delhi_bbox = geocode_city_bbox("Delhi")
    assert delhi_bbox == KNOWN_CITY_BOUNDS["delhi"]

    # Unknown city should gracefully return fallback
    unknown_bbox = geocode_city_bbox("NonExistentCityXYZ1234567")
    assert len(unknown_bbox) == 4

def test_gee_provider_status_reporting():
    ready, msg = gee_provider.is_available()
    assert isinstance(ready, bool)
    assert isinstance(msg, str)
    assert len(msg) > 0

def test_real_osm_building_coverage_calculation(monkeypatch):
    """
    Tests that building coverage is calculated as actual area of building polygons
    intersecting the grid cell divided by the cell's area in square metres.
    """
    bbox = (77.40, 23.20, 77.42, 23.22)
    cells = generate_spatial_grid(bbox, target_grid_size_m=1000, max_cells=4)
    cell = cells[0]

    # Create a mock building inside cell[0] covering a known fraction of the cell
    c_min_lon, c_min_lat = cell.min_lon, cell.min_lat
    c_max_lon, c_max_lat = cell.max_lon, cell.max_lat
    
    # Building covering half of the lon span and half of the lat span (~25% of the cell area)
    half_lon = c_min_lon + (c_max_lon - c_min_lon) * 0.5
    half_lat = c_min_lat + (c_max_lat - c_min_lat) * 0.5
    mock_bldg = box(c_min_lon, c_min_lat, half_lon, half_lat)

    monkeypatch.setattr(
        OpenGeospatialProvider,
        "_fetch_osm_buildings",
        lambda self, b, timeout=12.0: ([mock_bldg], True, None)
    )
    monkeypatch.setattr(
        OpenGeospatialProvider,
        "_fetch_osm_roads",
        lambda self, b, timeout=12.0: ([], True, None)
    )
    monkeypatch.setattr(
        OpenGeospatialProvider,
        "_fetch_real_surface_temperatures",
        lambda self, lats, lons: [32.0 for _ in lats]
    )

    df, meta = open_provider.acquire_features("Bhopal", bbox, cells)
    assert meta.provider == "open_geospatial"
    assert meta.synthetic_data is False
    
    # Cell 0 contains the building: should be approximately 0.25 (25% coverage)
    built_up_0 = df.loc[df["zone_id"] == cell.zone_id, "built_up"].iloc[0]
    assert 0.20 <= built_up_0 <= 0.30

def test_real_osm_road_density_calculation(monkeypatch):
    """
    Tests that road density is calculated from total road length inside each grid cell,
    normalized against ROAD_DENSITY_CEILING_KM_PER_KM2.
    """
    bbox = (77.40, 23.20, 77.42, 23.22)
    cells = generate_spatial_grid(bbox, target_grid_size_m=1000, max_cells=4)
    cell = cells[0]

    # Road crossing cell 0 from left to right
    road_line = LineString([
        (cell.min_lon, (cell.min_lat + cell.max_lat) / 2.0),
        (cell.max_lon, (cell.min_lat + cell.max_lat) / 2.0)
    ])

    monkeypatch.setattr(
        OpenGeospatialProvider,
        "_fetch_osm_buildings",
        lambda self, b, timeout=12.0: ([], True, None)
    )
    monkeypatch.setattr(
        OpenGeospatialProvider,
        "_fetch_osm_roads",
        lambda self, b, timeout=12.0: ([road_line], True, None)
    )
    monkeypatch.setattr(
        OpenGeospatialProvider,
        "_fetch_real_surface_temperatures",
        lambda self, lats, lons: [32.0 for _ in lats]
    )

    df, meta = open_provider.acquire_features("Bhopal", bbox, cells)
    road_density_0 = df.loc[df["zone_id"] == cell.zone_id, "road_density"].iloc[0]
    assert road_density_0 > 0.0
    assert road_density_0 <= 1.0

def test_osm_empty_responses(monkeypatch):
    """
    Tests that empty Overpass responses (zero buildings, zero roads) result in 0.0
    and are explicitly reported in metadata warnings rather than fabricating data.
    """
    bbox = (77.40, 23.20, 77.42, 23.22)
    cells = generate_spatial_grid(bbox, target_grid_size_m=1000, max_cells=2)

    monkeypatch.setattr(
        OpenGeospatialProvider,
        "_fetch_osm_buildings",
        lambda self, b, timeout=12.0: ([], True, None)
    )
    monkeypatch.setattr(
        OpenGeospatialProvider,
        "_fetch_osm_roads",
        lambda self, b, timeout=12.0: ([], True, None)
    )
    monkeypatch.setattr(
        OpenGeospatialProvider,
        "_fetch_real_surface_temperatures",
        lambda self, lats, lons: [30.0 for _ in lats]
    )

    df, meta = open_provider.acquire_features("Bhopal", bbox, cells)
    assert (df["built_up"] == 0.0).all()
    assert (df["road_density"] == 0.0).all()
    assert any("0 building features" in w for w in meta.warnings)
    assert any("0 road features" in w for w in meta.warnings)

def test_osm_api_failures_and_fallback(monkeypatch):
    """
    Tests that Overpass query timeouts / rate limits trigger explicit warnings
    in metadata when falling back.
    """
    bbox = (77.40, 23.20, 77.42, 23.22)
    cells = generate_spatial_grid(bbox, target_grid_size_m=1000, max_cells=2)

    monkeypatch.setattr(
        OpenGeospatialProvider,
        "_fetch_osm_buildings",
        lambda self, b, timeout=12.0: ([], False, "Overpass API gateway timeout.")
    )
    monkeypatch.setattr(
        OpenGeospatialProvider,
        "_fetch_osm_roads",
        lambda self, b, timeout=12.0: ([], False, "Overpass API rate limit reached (HTTP 429).")
    )
    monkeypatch.setattr(
        OpenGeospatialProvider,
        "_fetch_real_surface_temperatures",
        lambda self, lats, lons: [30.0 for _ in lats]
    )

    df, meta = open_provider.acquire_features("Bhopal", bbox, cells)
    assert any("OSM Buildings query failed: Overpass API gateway timeout" in w for w in meta.warnings)
    assert any("OSM Road network query failed" in w for w in meta.warnings)
    # Even on fallback, priority scores must remain normalized in [0, 1]
    assert df["built_up"].between(0.0, 1.0).all()
    assert df["road_density"].between(0.0, 1.0).all()

def test_satellite_pipeline_fallback():
    class FailingProvider(SatelliteDataProvider):
        name = "failing_mock"
        def is_available(self):
            return True, "Mock ready"
        def acquire_features(self, city, bbox, grid_cells):
            raise ConnectionError("Mock satellite server outage")

    bbox = (77.38, 23.22, 77.42, 23.26)
    cells = generate_spatial_grid(bbox, target_grid_size_m=1000, max_cells=4)
    
    # Test dummy provider acquisition
    df_dummy, meta_dummy = dummy_provider.acquire_features("Bhopal", bbox, cells)
    assert meta_dummy.synthetic_data is True
    assert len(df_dummy) == 500

def test_normalization_and_scoring_methods():
    raw_df = pd.DataFrame([{
        "zone_id": "T01",
        "lat": 23.25,
        "lon": 77.41,
        "lst_c": 35.0,
        "ndvi": 0.40,
        "built_up": 0.50,
        "road_density": 0.30,
        "green_area": 0.35,
        "exposure": 0.45
    }])
    
    # Reference normalization
    norm_ref = normalize_features(raw_df, method="reference")
    score_ref = calculate_priority(norm_ref)
    assert 0.0 <= score_ref["priority_score"].iloc[0] <= 1.0

    # Dataset relative
    norm_rel = normalize_features(raw_df, method="dataset_relative")
    score_rel = calculate_priority(norm_rel)
    assert 0.0 <= score_rel["priority_score"].iloc[0] <= 1.0

def test_dataframe_validation_error():
    bad_df = pd.DataFrame([{"zone_id": "Z1", "lat": 23.0}])
    with pytest.raises(ValueError, match="Missing required columns"):
        validate_dataframe(bad_df)

def test_osm_headers_sent(monkeypatch):
    """
    Verifies that _fetch_osm_buildings and _fetch_osm_roads send NOMINATIM_USER_AGENT
    and Accept: application/json in their POST request headers.
    """
    from app.config import NOMINATIM_USER_AGENT
    import httpx

    captured_headers = []

    def mock_post(self, url, *args, **kwargs):
        headers = kwargs.get("headers", {})
        captured_headers.append(headers)
        # Return mock 200 response with empty elements
        return httpx.Response(200, json={"elements": []}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    bbox = (77.40, 23.20, 77.42, 23.22)
    provider = OpenGeospatialProvider()
    
    # Test buildings request
    provider._fetch_osm_buildings(bbox)
    assert len(captured_headers) == 1
    assert captured_headers[0]["User-Agent"] == NOMINATIM_USER_AGENT
    assert captured_headers[0]["Accept"] == "application/json"

    # Test roads request
    provider._fetch_osm_roads(bbox)
    assert len(captured_headers) == 2
    assert captured_headers[1]["User-Agent"] == NOMINATIM_USER_AGENT
    assert captured_headers[1]["Accept"] == "application/json"

def test_osm_http_406_handled(monkeypatch):
    """
    Verifies that HTTP 406 responses from Overpass are safely handled
    without unhandled exceptions, and explicit warnings are added to metadata.
    """
    import httpx

    def mock_post_406(self, url, *args, **kwargs):
        return httpx.Response(406, text="406 Not Acceptable", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.Client, "post", mock_post_406)

    bbox = (77.40, 23.20, 77.42, 23.22)
    provider = OpenGeospatialProvider()

    # Direct function checks
    _, b_ok, b_err = provider._fetch_osm_buildings(bbox)
    assert b_ok is False
    assert "406" in b_err

    _, r_ok, r_err = provider._fetch_osm_roads(bbox)
    assert r_ok is False
    assert "406" in r_err

    # acquire_features integration check
    monkeypatch.setattr(
        OpenGeospatialProvider,
        "_fetch_real_surface_temperatures",
        lambda self, lats, lons: [31.0 for _ in lats]
    )
    cells = generate_spatial_grid(bbox, target_grid_size_m=1000, max_cells=2)
    df, meta = provider.acquire_features("Bhopal", bbox, cells)
    assert any("406" in w for w in meta.warnings)
    assert df["built_up"].between(0.0, 1.0).all()
    assert df["road_density"].between(0.0, 1.0).all()

def test_quadrant_boundaries():
    """
    Verifies that split_bbox_into_quadrants correctly divides a bounding box into
    four non-overlapping quadrants (SW, SE, NW, NE) preserving coordinate order.
    """
    from app.services.satellite.open_geo_provider import split_bbox_into_quadrants

    bbox = (10.0, 20.0, 12.0, 24.0)
    quads = split_bbox_into_quadrants(bbox)
    quad_dict = dict(quads)

    assert len(quads) == 4
    assert set(quad_dict.keys()) == {"SW", "SE", "NW", "NE"}

    # SW: min_lon, min_lat, mid_lon, mid_lat
    assert quad_dict["SW"] == (10.0, 20.0, 11.0, 22.0)
    # SE: mid_lon, min_lat, max_lon, mid_lat
    assert quad_dict["SE"] == (11.0, 20.0, 12.0, 22.0)
    # NW: min_lon, mid_lat, mid_lon, max_lat
    assert quad_dict["NW"] == (10.0, 22.0, 11.0, 24.0)
    # NE: mid_lon, mid_lat, max_lon, max_lat
    assert quad_dict["NE"] == (11.0, 22.0, 12.0, 24.0)

    # Validate coordinate ordering for all quadrants
    for name, (q_min_lon, q_min_lat, q_max_lon, q_max_lat) in quads:
        assert q_min_lon < q_max_lon
        assert q_min_lat < q_max_lat
        assert 10.0 <= q_min_lon <= 12.0
        assert 20.0 <= q_min_lat <= 24.0

def test_adaptive_quadrant_result_merging_and_deduplication(monkeypatch):
    """
    Verifies that building geometries from multiple quadrants are correctly merged
    and that duplicate buildings along quadrant boundaries are deduplicated by OSM element ID.
    """
    provider = OpenGeospatialProvider()
    bbox = (-74.05, 40.68, -73.85, 40.85)  # Large bbox (triggers quadrants)

    # Building geometry template
    def make_elem(eid, lon, lat):
        return {
            "id": eid,
            "type": "way",
            "geometry": [
                {"lon": lon, "lat": lat},
                {"lon": lon + 0.001, "lat": lat},
                {"lon": lon + 0.001, "lat": lat + 0.001},
                {"lon": lon, "lat": lat}
            ]
        }

    # SW contains 101 and boundary building 102
    # SE contains boundary building 102 (duplicate) and 103
    # NW contains 104
    # NE contains 105
    quad_responses = {
        "SW": [make_elem(101, -74.01, 40.70), make_elem(102, -73.95, 40.765)],
        "SE": [make_elem(102, -73.95, 40.765), make_elem(103, -73.90, 40.70)],
        "NW": [make_elem(104, -74.01, 40.80)],
        "NE": [make_elem(105, -73.90, 40.80)],
    }

    call_index = 0
    quad_names = ["SW", "SE", "NW", "NE"]

    def mock_query(self, q_bbox, timeout=30.0):
        nonlocal call_index
        q_name = quad_names[call_index % 4]
        call_index += 1
        return quad_responses[q_name], True, None, 200

    monkeypatch.setattr(OpenGeospatialProvider, "_query_overpass_building_elements", mock_query)

    buildings, b_ok, b_err = provider._fetch_osm_buildings(bbox)
    assert b_ok is True
    assert b_err is None
    # 5 unique buildings (101, 102, 103, 104, 105), building 102 deduplicated
    assert len(buildings) == 5

def test_http_504_fallback_to_quadrants(monkeypatch):
    """
    Verifies that when a single monolithic query fails with HTTP 504 / timeout,
    the provider automatically falls back to adaptive quadrant chunking and recovers.
    """
    provider = OpenGeospatialProvider()
    bbox = (77.40, 23.20, 77.42, 23.22)  # Small bbox

    single_attempted = False
    quadrant_calls = 0

    def mock_query(self, query_bbox, timeout=30.0):
        nonlocal single_attempted, quadrant_calls
        if query_bbox == bbox:
            single_attempted = True
            # Single query times out with HTTP 504
            return [], False, "Overpass API gateway timeout (HTTP 504).", 504
        else:
            quadrant_calls += 1
            # Quadrants succeed
            elem = {
                "id": 200 + quadrant_calls,
                "type": "way",
                "geometry": [
                    {"lon": query_bbox[0] + 0.001, "lat": query_bbox[1] + 0.001},
                    {"lon": query_bbox[0] + 0.002, "lat": query_bbox[1] + 0.001},
                    {"lon": query_bbox[0] + 0.002, "lat": query_bbox[1] + 0.002},
                    {"lon": query_bbox[0] + 0.001, "lat": query_bbox[1] + 0.001}
                ]
            }
            return [elem], True, None, 200

    monkeypatch.setattr(OpenGeospatialProvider, "_query_overpass_building_elements", mock_query)

    buildings, b_ok, b_err = provider._fetch_osm_buildings(bbox)
    assert single_attempted is True
    assert quadrant_calls == 4
    assert b_ok is True
    assert b_err is None
    assert len(buildings) == 4

def test_partial_quadrant_failure(monkeypatch):
    """
    Verifies that if one or more quadrants fail (e.g. HTTP 504) while others succeed,
    the provider:
    1. Returns the real geometries retrieved from the successful quadrants.
    2. Reports the failed quadrant and partial status in error/warning metadata.
    3. acquire_features calculates building coverage from the available real geometries.
    """
    provider = OpenGeospatialProvider()
    bbox = (-74.05, 40.68, -73.85, 40.85)  # Large bbox

    call_index = 0
    quad_names = ["SW", "SE", "NW", "NE"]

    def mock_query(self, query_bbox, timeout=30.0):
        nonlocal call_index
        q_name = quad_names[call_index % 4]
        call_index += 1
        if q_name == "NE":
            # NE fails with HTTP 504
            return [], False, "Overpass API gateway timeout (HTTP 504).", 504
        else:
            elem = {
                "id": 300 + call_index,
                "type": "way",
                "geometry": [
                    {"lon": query_bbox[0] + 0.001, "lat": query_bbox[1] + 0.001},
                    {"lon": query_bbox[0] + 0.002, "lat": query_bbox[1] + 0.001},
                    {"lon": query_bbox[0] + 0.002, "lat": query_bbox[1] + 0.002},
                    {"lon": query_bbox[0] + 0.001, "lat": query_bbox[1] + 0.001}
                ]
            }
            return [elem], True, None, 200

    monkeypatch.setattr(OpenGeospatialProvider, "_query_overpass_building_elements", mock_query)

    buildings, b_ok, b_err = provider._fetch_osm_buildings(bbox)
    assert b_ok is True
    assert len(buildings) == 3
    assert b_err is not None
    assert "Partial building coverage: quadrant(s) failed" in b_err
    assert "NE:" in b_err

    # Test integration with acquire_features
    monkeypatch.setattr(
        OpenGeospatialProvider,
        "_fetch_osm_roads",
        lambda self, b, timeout=12.0: ([], True, None)
    )
    monkeypatch.setattr(
        OpenGeospatialProvider,
        "_fetch_real_surface_temperatures",
        lambda self, lats, lons: [30.0 for _ in lats]
    )
    cells = generate_spatial_grid(bbox, target_grid_size_m=2000, max_cells=4)
    df, meta = provider.acquire_features("New York", bbox, cells)

    assert any("Partial building coverage: quadrant(s) failed" in w for w in meta.warnings)
    assert any("NE:" in w for w in meta.warnings)
    assert "partial building footprints" in meta.satellite_source
    assert df["built_up"].between(0.0, 1.0).all()

def test_all_quadrants_failure(monkeypatch):
    """
    Verifies that when all quadrants fail, the provider marks building data as
    unavailable, falls back to estimated building density, and explicitly records
    the failure in metadata.warnings.
    """
    provider = OpenGeospatialProvider()
    bbox = (-74.05, 40.68, -73.85, 40.85)

    def mock_query(self, query_bbox, timeout=30.0):
        return [], False, "Overpass API gateway timeout (HTTP 504).", 504

    monkeypatch.setattr(OpenGeospatialProvider, "_query_overpass_building_elements", mock_query)

    buildings, b_ok, b_err = provider._fetch_osm_buildings(bbox)
    assert b_ok is False
    assert len(buildings) == 0
    assert "All building quadrants failed" in b_err

    # Test acquire_features integration
    monkeypatch.setattr(
        OpenGeospatialProvider,
        "_fetch_osm_roads",
        lambda self, b, timeout=12.0: ([], True, None)
    )
    monkeypatch.setattr(
        OpenGeospatialProvider,
        "_fetch_real_surface_temperatures",
        lambda self, lats, lons: [30.0 for _ in lats]
    )
    cells = generate_spatial_grid(bbox, target_grid_size_m=2000, max_cells=4)
    df, meta = provider.acquire_features("New York", bbox, cells)

    assert any("All building quadrants failed" in w for w in meta.warnings)
    assert "OpenStreetMap buildings unavailable" in meta.satellite_source
    assert df["built_up"].between(0.0, 1.0).all()

