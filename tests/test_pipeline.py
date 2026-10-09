from app.pipeline import run_analysis, build_geojson

def test_analysis_scores_and_categories():
    result = run_analysis()
    assert len(result) == 500
    assert result["priority_score"].between(0,1).all()
    assert set(result["category"].astype(str)).issubset({"Low","Medium","High"})

def test_every_zone_has_recommendations():
    result = run_analysis()
    assert result["recommendations"].map(lambda x: isinstance(x,list) and len(x)>0).all()

def test_geojson_output():
    geojson = build_geojson(run_analysis().head(3))
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) == 3
