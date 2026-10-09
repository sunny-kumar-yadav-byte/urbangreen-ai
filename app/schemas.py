from typing import Any, Literal
from pydantic import BaseModel, Field

GeometryType = Literal["Polygon", "Point"]
NormalizationMethod = Literal["reference", "dataset_relative"]
PriorityCategory = Literal["Low", "Medium", "High"]

class GeoJSONGeometry(BaseModel):
    type: Literal["Point", "Polygon"]
    coordinates: list[Any]

class RecommendationDetail(BaseModel):
    action: str
    category: str = Field(description="Intervention classification: Canopy, Cool Surface, Mobility, etc.")
    urgency: Literal["Critical", "High", "Medium", "Maintenance"]
    rationale: str

class ZoneFeatureInput(BaseModel):
    """Schema for accepting externally ingested or GIS-derived features for a zone."""
    zone_id: str
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)
    lst_c: float = Field(description="Land surface temperature in Celsius")
    ndvi: float = Field(ge=-1.0, le=1.0, description="Normalized Difference Vegetation Index")
    built_up: float = Field(ge=0.0, le=1.0, description="Impervious surface / built-up ratio")
    road_density: float = Field(ge=0.0, le=1.0, description="Road network density ratio")
    green_area: float = Field(ge=0.0, le=1.0, description="Vegetated and tree-covered land area ratio")
    exposure: float = Field(ge=0.0, le=1.0, description="Solar / thermal / population exposure index")
    polygon_coordinates: list[list[list[float]]] | None = Field(
        default=None,
        description="Optional GeoJSON polygon exterior ring coordinates [[[lon, lat], ...]]"
    )

class DataSourceMetadata(BaseModel):
    provider: str
    synthetic_data: bool
    satellite_source: str | None = None
    acquisition_date: str | None = None
    resolution_meters: int | None = None
    bounding_box: list[float] | None = None
    warnings: list[str] = Field(default_factory=list)
    notice: str

class ZoneRecord(BaseModel):
    zone_id: str
    lat: float
    lon: float
    priority_score: float
    category: PriorityCategory
    recommendations: list[str]
    recommendation_details: list[RecommendationDetail] = Field(default_factory=list)
    indicators: dict[str, float]
    raw_metrics: dict[str, float] = Field(default_factory=dict)
    polygon_coordinates: list[list[list[float]]] | None = None

    # Frontend compatibility fields
    latitude: float | None = None
    longitude: float | None = None
    location: str | None = None
    locality: str | None = None
    grid_size: str | None = None
    lst: float | None = None
    ndvi: float | None = None
    built_up: float | None = None
    road_density: float | None = None
    priority: str | None = None
    recommendation: str | None = None
    satellite_url: str | None = None

class AnalyzeRequest(BaseModel):
    city: str = Field(default="Bhopal", min_length=1, max_length=100)
    bbox: list[float] | None = Field(
        default=None,
        description="Optional explicit bounding box [min_lon, min_lat, max_lon, max_lat]"
    )
    grid_size_m: int = Field(default=500, ge=100, le=5000, description="Target grid cell size in meters")
    force_synthetic: bool = Field(default=False, description="Explicitly use synthetic benchmark dataset")
    normalization_method: NormalizationMethod = Field(
        default="reference",
        description="'reference' uses fixed geographic bounds across cities; 'dataset_relative' scales strictly within the query."
    )

class IngestCustomZonesRequest(BaseModel):
    city: str = Field(min_length=1, max_length=100)
    zones: list[ZoneFeatureInput] = Field(min_length=1)
    normalization_method: NormalizationMethod = "reference"

class WhatIfRequest(BaseModel):
    zone_id: str
    changes: dict[str, float] = Field(
        description="Feature adjustments between 0.0 and 1.0 (e.g. {'heat': 0.3, 'ndvi': 0.7})"
    )

class WhatIfResponse(BaseModel):
    zone_id: str
    baseline_score: float
    scenario_score: float
    score_change: float
    baseline_category: PriorityCategory
    scenario_category: PriorityCategory
    baseline_recommendations: list[str]
    scenario_recommendations: list[str]
    scenario_recommendation_details: list[RecommendationDetail]
    notice: str

class AnalyzeResponse(BaseModel):
    city: str
    data_source: str
    synthetic_data: bool
    metadata: DataSourceMetadata
    total_zones: int
    summary: dict[str, int]
    zones: list[ZoneRecord]
    notice: str

    # Frontend compatibility fields
    avg_lst: float | None = None
    avg_ndvi: float | None = None
    high_priority_zones: int | None = None
    priority_index: float | None = None
    built_up: float | None = None
    zone: ZoneRecord | None = None
    high_priority_zone_list: list[ZoneRecord] | None = None
