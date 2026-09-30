import json
from pathlib import Path

import pytest

from heat_atlas.autocorrelation import (
    centroids_and_values,
    correlation_length,
    correlogram,
    effective_sample_size,
)


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "web" / "public" / "data" / "grids.geojson"

# At 32 degrees north these steps are 500 m on the ground.
LON_STEP = 0.005303
LAT_STEP = 0.004522


def _ramp_grid(rows: int = 40, cols: int = 40) -> tuple[list[tuple[float, float]], list[float]]:
    """A field that depends only on the column index: smooth, so autocorrelated."""
    points = [(118.7 + col * LON_STEP, 32.0 + row * LAT_STEP) for row in range(rows) for col in range(cols)]
    return points, [float(col) for _ in range(rows) for col in range(cols)]


def _feature(lon: float, lat: float, value: float) -> dict:
    ring = [[lon, lat], [lon + LON_STEP, lat], [lon + LON_STEP, lat + LAT_STEP], [lon, lat + LAT_STEP], [lon, lat]]
    return {"type": "Feature", "properties": {"lst_mean_c": value}, "geometry": {"type": "Polygon", "coordinates": [ring]}}


def test_centroids_and_values_reads_ring_centres():
    geojson = {"type": "FeatureCollection", "features": [_feature(118.7, 32.0, 41.5)]}
    points, values = centroids_and_values(geojson, "lst_mean_c")
    assert len(points) == len(values) == 1
    assert values == [41.5]
    assert abs(points[0][0] - (118.7 + LON_STEP / 2)) < 1e-9
    assert abs(points[0][1] - (32.0 + LAT_STEP / 2)) < 1e-9


def test_centroids_and_values_rejects_empty_rings():
    geojson = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"lst_mean_c": 40.0}, "geometry": {"type": "Polygon", "coordinates": [[]]}},
    ]}
    with pytest.raises(ValueError, match="empty ring"):
        centroids_and_values(geojson, "lst_mean_c")


def test_correlogram_rejects_constant_and_tiny_fields():
    points, values = _ramp_grid(rows=2, cols=6)
    with pytest.raises(ValueError, match="constant"):
        correlogram(points, [5.0] * len(points))
    with pytest.raises(ValueError, match="three grids"):
        correlogram(points[:2], values[:2])


def test_correlogram_decays_with_distance_on_a_smooth_field():
    points, values = _ramp_grid()
    entries = correlogram(points, values, max_lag_m=5000.0, min_pairs=50)
    assert entries
    assert all(0 < entry["lag_m"] <= 5000.0 for entry in entries)
    assert entries[0]["correlation"] > 0.9
    assert entries[-1]["correlation"] < entries[0]["correlation"]


def test_correlogram_drops_bands_that_are_too_sparse():
    points, values = _ramp_grid(rows=4, cols=4)
    with pytest.raises(ValueError, match="enough pairs"):
        correlogram(points, values, max_lag_m=5000.0, min_pairs=10_000)


def test_correlation_length_interpolates_between_bands():
    entries = [
        {"lag_m": 1000.0, "correlation": 0.8, "pairs": 500},
        {"lag_m": 2000.0, "correlation": 0.2, "pairs": 500},
    ]
    assert abs(correlation_length(entries, 0.5) - 1500.0) < 1e-9
    assert correlation_length([{"lag_m": 500.0, "correlation": 0.3, "pairs": 500}], 0.5) == 500.0
    with pytest.raises(ValueError, match="never fell below"):
        correlation_length([{"lag_m": 500.0, "correlation": 0.9, "pairs": 500}], 0.5)


def test_effective_sample_size_scales_with_spacing_over_length():
    assert abs(effective_sample_size(2046, 500.0, 1303.0) - 301.3) < 1.0
    assert effective_sample_size(1000, 500.0, 500.0) == 1000.0
    with pytest.raises(ValueError, match="positive"):
        effective_sample_size(1000, 500.0, 0.0)


def test_committed_grids_are_strongly_autocorrelated():
    """The published correlation must not be read as an inference at n = 2046."""
    geojson = json.loads(DATA.read_text(encoding="utf-8"))
    points, values = centroids_and_values(geojson, "lst_mean_c")
    entries = correlogram(points, values)
    length = correlation_length(entries, 0.5)
    effective = effective_sample_size(len(points), 500.0, length)
    assert 500 < length < 4000
    assert effective < len(points) / 3
