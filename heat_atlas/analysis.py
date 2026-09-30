"""Pure scientific transforms and grid aggregation.

Landsat Collection 2 Level-2 scaling values come from the asset metadata.
The QA mask rejects fill, cloud-related pixels, snow, and water.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from pyproj import Transformer


QA_REJECT_BITS = (0, 1, 2, 3, 4, 5, 7)
QA_REJECT_MASK = sum(1 << bit for bit in QA_REJECT_BITS)
LST_SCALE = 0.00341802
LST_OFFSET_K = 149.0
REFLECTANCE_SCALE = 0.0000275
REFLECTANCE_OFFSET = -0.2


@dataclass(frozen=True)
class AnalysisResult:
    features: list[dict]
    valid_pixels: int
    total_pixels: int
    summary: dict


def valid_pixel_mask(qa: np.ndarray, lst_raw: np.ndarray, red_raw: np.ndarray, nir_raw: np.ndarray) -> np.ndarray:
    """Return valid land pixels for the three measurements."""
    if not (qa.shape == lst_raw.shape == red_raw.shape == nir_raw.shape):
        raise ValueError("All input bands must have the same shape")
    return (
        ((qa.astype(np.uint16) & QA_REJECT_MASK) == 0)
        & (lst_raw > 0)
        & (red_raw > 0)
        & (nir_raw > 0)
    )


def calculate_indices(lst_raw: np.ndarray, red_raw: np.ndarray, nir_raw: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Convert surface temperature to Celsius and reflectance to NDVI."""
    lst_c = lst_raw.astype(np.float32) * LST_SCALE + LST_OFFSET_K - 273.15
    red = red_raw.astype(np.float32) * REFLECTANCE_SCALE + REFLECTANCE_OFFSET
    nir = nir_raw.astype(np.float32) * REFLECTANCE_SCALE + REFLECTANCE_OFFSET
    denominator = nir + red
    ndvi = np.full(red.shape, np.nan, dtype=np.float32)
    np.divide(nir - red, denominator, out=ndvi, where=denominator > 0.02)
    ndvi[(red < 0) | (nir < 0) | (red > 1) | (nir > 1)] = np.nan
    return lst_c, ndvi


def aggregate_grid(
    lst_c: np.ndarray,
    ndvi: np.ndarray,
    base_mask: np.ndarray,
    transform,
    crs,
    *,
    grid_metres: int = 500,
    min_coverage: float = 0.60,
    green_threshold: float = 0.30,
) -> AnalysisResult:
    """Aggregate pixels to a projected square grid and export WGS84 polygons."""
    if grid_metres <= 0:
        raise ValueError("grid_metres must be positive")
    if not (lst_c.shape == ndvi.shape == base_mask.shape):
        raise ValueError("Values and mask must have the same shape")
    rows, cols = lst_c.shape
    rr, cc = np.indices((rows, cols), dtype=np.float64)
    x = transform.c + transform.a * (cc + 0.5) + transform.b * (rr + 0.5)
    y = transform.f + transform.d * (cc + 0.5) + transform.e * (rr + 0.5)
    origin_x = math.floor(float(np.min(x)) / grid_metres) * grid_metres
    origin_y = math.floor(float(np.min(y)) / grid_metres) * grid_metres
    gx = np.floor((x - origin_x) / grid_metres).astype(np.int32)
    gy = np.floor((y - origin_y) / grid_metres).astype(np.int32)
    nx = int(gx.max()) + 1
    ny = int(gy.max()) + 1
    slot = gy * nx + gx
    nslots = nx * ny
    total = np.bincount(slot.ravel(), minlength=nslots)
    valid = base_mask & np.isfinite(lst_c) & np.isfinite(ndvi) & (ndvi >= -1) & (ndvi <= 1)
    indices = slot[valid].ravel()
    valid_count = np.bincount(indices, minlength=nslots)
    lst_sum = np.bincount(indices, weights=lst_c[valid].astype(np.float64), minlength=nslots)
    ndvi_sum = np.bincount(indices, weights=ndvi[valid].astype(np.float64), minlength=nslots)
    green_count = np.bincount(indices, weights=(ndvi[valid] >= green_threshold).astype(np.int8), minlength=nslots)

    if not valid_count.any():
        raise ValueError("No valid land pixels remained after masking")
    hot_threshold = float(np.percentile(lst_c[valid], 75))
    hot_count = np.bincount(indices, weights=(lst_c[valid] >= hot_threshold).astype(np.int8), minlength=nslots)
    to_wgs84 = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    features: list[dict] = []
    for cell in range(nslots):
        count = int(valid_count[cell])
        coverage = count / int(total[cell]) if total[cell] else 0
        if count < 25 or coverage < min_coverage:
            continue
        cy, cx = divmod(cell, nx)
        x0 = origin_x + cx * grid_metres
        y0 = origin_y + cy * grid_metres
        corners = [(x0, y0), (x0 + grid_metres, y0), (x0 + grid_metres, y0 + grid_metres), (x0, y0 + grid_metres), (x0, y0)]
        ring = [[round(lon, 6), round(lat, 6)] for lon, lat in (to_wgs84.transform(px, py) for px, py in corners)]
        features.append({
            "type": "Feature",
            "id": f"g{cx}-{cy}",
            "properties": {
                "lst_mean_c": round(float(lst_sum[cell] / count), 2),
                "ndvi_mean": round(float(ndvi_sum[cell] / count), 3),
                "green_share_pct": round(float(green_count[cell] / count * 100), 1),
                "hot_share_pct": round(float(hot_count[cell] / count * 100), 1),
                "coverage_pct": round(coverage * 100, 1),
                "valid_pixels": count,
            },
            "geometry": {"type": "Polygon", "coordinates": [ring]},
        })

    temperatures = np.array([f["properties"]["lst_mean_c"] for f in features], dtype=np.float64)
    vegetation = np.array([f["properties"]["ndvi_mean"] for f in features], dtype=np.float64)
    correlation = float(np.corrcoef(vegetation, temperatures)[0, 1]) if len(features) > 2 and np.std(temperatures) > 0 and np.std(vegetation) > 0 else None
    summary = {
        "grid_count": len(features),
        "grid_metres": grid_metres,
        "lst_mean_c": round(float(np.mean(lst_c[valid])), 2),
        "lst_p10_c": round(float(np.percentile(lst_c[valid], 10)), 2),
        "lst_p90_c": round(float(np.percentile(lst_c[valid], 90)), 2),
        "hot_threshold_c": round(hot_threshold, 2),
        "ndvi_mean": round(float(np.mean(ndvi[valid])), 3),
        "grid_ndvi_lst_correlation": round(correlation, 3) if correlation is not None else None,
    }
    return AnalysisResult(features, int(valid.sum()), rows * cols, summary)
