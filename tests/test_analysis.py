import numpy as np
from rasterio import Affine

from heat_atlas.analysis import (
    QA_REJECT_BITS,
    aggregate_grid,
    calculate_indices,
    valid_pixel_mask,
)


def test_qa_mask_excludes_documented_reject_bits_and_missing_data():
    qa = np.array([[0] + [1 << bit for bit in QA_REJECT_BITS]], dtype=np.uint16)
    raw = np.full(qa.shape, 40000, dtype=np.uint16)
    mask = valid_pixel_mask(qa, raw, raw, raw)
    assert mask.tolist() == [[True] + [False] * len(QA_REJECT_BITS)]
    raw[0, 0] = 0
    assert not valid_pixel_mask(qa, raw, raw, raw).any()


def test_landsat_collection_two_scaling_and_ndvi():
    thermal = np.array([[44000]], dtype=np.uint16)
    red = np.array([[12000]], dtype=np.uint16)
    nir = np.array([[22000]], dtype=np.uint16)
    lst, ndvi = calculate_indices(thermal, red, nir)
    assert np.isclose(lst[0, 0], 44000 * 0.00341802 + 149 - 273.15, atol=0.001)
    red_reflectance = 12000 * 0.0000275 - 0.2
    nir_reflectance = 22000 * 0.0000275 - 0.2
    assert np.isclose(ndvi[0, 0], (nir_reflectance - red_reflectance) / (nir_reflectance + red_reflectance), atol=0.0001)


def test_grid_aggregation_exports_projected_500m_polygons():
    temperature = np.full((40, 40), 32.0, dtype=np.float32)
    ndvi = np.full((40, 40), 0.42, dtype=np.float32)
    mask = np.ones((40, 40), dtype=bool)
    mask[0:10, 0:10] = False
    transform = Affine(30, 0, 600000, 0, -30, 3560000)
    result = aggregate_grid(temperature, ndvi, mask, transform, "EPSG:32650")
    assert result.valid_pixels == 1500
    assert result.total_pixels == 1600
    assert result.features
    assert result.summary["grid_metres"] == 500
    assert all(f["properties"]["coverage_pct"] >= 60 for f in result.features)
    assert all(abs(f["properties"]["lst_mean_c"] - 32) < 0.01 for f in result.features)
    assert all(-180 < f["geometry"]["coordinates"][0][0][0] < 180 for f in result.features)


def test_grid_aggregation_fails_on_all_invalid_pixels():
    temperature = np.ones((20, 20), dtype=np.float32)
    ndvi = np.ones((20, 20), dtype=np.float32)
    mask = np.zeros((20, 20), dtype=bool)
    try:
        aggregate_grid(temperature, ndvi, mask, Affine(30, 0, 600000, 0, -30, 3560000), "EPSG:32650")
    except ValueError as exc:
        assert "No valid land pixels" in str(exc)
    else:
        raise AssertionError("Expected a useful error for an all-invalid scene")
