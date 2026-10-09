import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_home_and_health():
    res_home = client.get("/")
    assert res_home.status_code == 200
    data = res_home.json()
    assert data["message"] == "UrbanGreen AI API"
    assert "providers" in data

    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json() == {"status": "healthy"}

def test_satellite_status():
    res = client.get("/satellite/status")
    assert res.status_code == 200
    data = res.json()
    assert "active_primary_provider" in data
    assert len(data["providers"]) >= 3

def test_analyze_city_synthetic():
    res = client.post("/analyze-city", json={"city": "Bhopal", "force_synthetic": True})
    assert res.status_code == 200
    data = res.json()
    assert data["city"] == "Bhopal"
    assert data["synthetic_data"] is True
    assert data["total_zones"] == 500
    assert "High" in data["summary"]
    assert len(data["zones"]) == 500
    sample = data["zones"][0]
    assert "zone_id" in sample
    assert "priority_score" in sample
    assert "recommendations" in sample
    assert "indicators" in sample

def test_analyze_city_real_pipeline(monkeypatch):
    from app.services.satellite.open_geo_provider import OpenGeospatialProvider
    from shapely.geometry import Polygon, LineString

    mock_poly = Polygon([[77.40, 23.20], [77.41, 23.20], [77.41, 23.21], [77.40, 23.21], [77.40, 23.20]])
    mock_line = LineString([[77.40, 23.20], [77.42, 23.22]])

    monkeypatch.setattr(
        OpenGeospatialProvider,
        "_fetch_osm_buildings",
        lambda self, b, timeout=12.0: ([mock_poly], True, None)
    )
    monkeypatch.setattr(
        OpenGeospatialProvider,
        "_fetch_osm_roads",
        lambda self, b, timeout=12.0: ([mock_line], True, None)
    )
    monkeypatch.setattr(
        OpenGeospatialProvider,
        "_fetch_real_surface_temperatures",
        lambda self, lats, lons: [33.8 + (i * 0.1) for i in range(len(lats))]
    )

    # Tests real geospatial/satellite pipeline
    res = client.post("/analyze-city", json={
        "city": "Bhopal",
        "force_synthetic": False,
        "grid_size_m": 1500
    })
    assert res.status_code == 200
    data = res.json()
    assert data["city"] == "Bhopal"
    assert data["total_zones"] > 0
    # Every zone in real mode must have polygon coordinates
    sample = data["zones"][0]
    assert sample["polygon_coordinates"] is not None
    assert len(sample["polygon_coordinates"][0]) >= 4
    assert 0.0 <= sample["priority_score"] <= 1.0
    assert "built_up" in sample["indicators"]
    assert "road_density" in sample["indicators"]

def test_satellite_service_failure_fallback(monkeypatch):
    from app.services.satellite.open_geo_provider import OpenGeospatialProvider
    def mock_failure(*args, **kwargs):
        raise ConnectionError("Satellite provider API unreachable")
        
    monkeypatch.setattr(OpenGeospatialProvider, "acquire_features", mock_failure)

    res = client.post("/analyze-city", json={
        "city": "Bhopal",
        "force_synthetic": False
    })
    assert res.status_code == 200
    data = res.json()
    assert data["synthetic_data"] is True
    assert any("Satellite provider API unreachable" in w for w in data["metadata"]["warnings"])

def test_analyze_city_invalid_input():
    # Empty city
    res_empty = client.post("/analyze-city", json={"city": ""})
    assert res_empty.status_code == 422

    # Grid size out of bounds (< 100 or > 5000)
    res_invalid_grid = client.post("/analyze-city", json={"city": "Bhopal", "grid_size_m": 50})
    assert res_invalid_grid.status_code == 422

def test_zones_filtering():
    # First ensure an analysis exists
    client.post("/analyze-city", json={"city": "Bhopal", "force_synthetic": True})
    
    res = client.get("/zones?category=High&limit=5")
    assert res.status_code == 200
    data = res.json()
    assert len(data["zones"]) <= 5
    for z in data["zones"]:
        assert z["category"] == "High"

def test_zones_geojson_polygon_and_point():
    # Polygon output
    res_poly = client.get("/zones.geojson?geometry_type=polygon")
    assert res_poly.status_code == 200
    geo_poly = res_poly.json()
    assert geo_poly["type"] == "FeatureCollection"
    assert len(geo_poly["features"]) > 0
    first_geom_type = geo_poly["features"][0]["geometry"]["type"]
    assert first_geom_type in ["Polygon", "Point"]

    # Point output
    res_pt = client.get("/zones.geojson?geometry_type=point")
    assert res_pt.status_code == 200
    geo_pt = res_pt.json()
    assert geo_pt["type"] == "FeatureCollection"
    assert geo_pt["features"][0]["geometry"]["type"] == "Point"

def test_what_if_simulation():
    # Run analysis first
    client.post("/analyze-city", json={"city": "Bhopal", "force_synthetic": True})

    # Valid simulation
    res = client.post("/what-if", json={
        "zone_id": "Z001",
        "changes": {"heat": 0.15, "ndvi": 0.85}
    })
    assert res.status_code == 200
    data = res.json()
    assert data["zone_id"] == "Z001"
    assert "baseline_score" in data
    assert "scenario_score" in data
    assert "score_change" in data
    assert len(data["scenario_recommendations"]) > 0

    # Invalid feature name
    res_invalid_feat = client.post("/what-if", json={
        "zone_id": "Z001",
        "changes": {"unknown_feature": 0.5}
    })
    assert res_invalid_feat.status_code == 422

    # Out of bounds value (> 1.0)
    res_out_of_bounds = client.post("/what-if", json={
        "zone_id": "Z001",
        "changes": {"heat": 1.5}
    })
    assert res_out_of_bounds.status_code == 422

    # Unknown zone ID
    res_unknown_zone = client.post("/what-if", json={
        "zone_id": "NON_EXISTENT_999",
        "changes": {"heat": 0.5}
    })
    assert res_unknown_zone.status_code == 404

def test_ingest_custom_gis():
    payload = {
        "city": "TestGISCity",
        "zones": [
            {
                "zone_id": "GIS_01",
                "lat": 23.25,
                "lon": 77.41,
                "lst_c": 38.5,
                "ndvi": 0.15,
                "built_up": 0.82,
                "road_density": 0.75,
                "green_area": 0.08,
                "exposure": 0.70,
                "polygon_coordinates": [[[77.40, 23.24], [77.42, 23.24], [77.42, 23.26], [77.40, 23.26], [77.40, 23.24]]]
            }
        ]
    }
    res = client.post("/ingest-gis", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["city"] == "TestGISCity"
    assert data["total_zones"] == 1
    assert data["zones"][0]["category"] == "High"
    assert "tree canopy" in " ".join(data["zones"][0]["recommendations"]).lower()
