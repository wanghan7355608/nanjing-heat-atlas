"""Spatial autocorrelation of the published grid statistics.

Grid count is not sample size. Neighbouring 500 m cells share the same terrain,
street layout and air mass, so the 2046 published grids carry far less
independent information than 2046 independent observations would. This module
estimates a correlation length from the derived GeoJSON and converts it into an
order-of-magnitude effective sample size, so that the correlation reported in
``manifest.json`` is never mistaken for an inference at n = grid count.

Standard library only: it runs on the committed derived data without the
raster stack or a network connection.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


METRES_PER_DEGREE_LAT = 110574.0
METRES_PER_DEGREE_LON = 111320.0


def centroids_and_values(geojson: dict, field: str) -> tuple[list[tuple[float, float]], list[float]]:
    """Return WGS84 ring centroids and one numeric property per feature.

    Parsing only: whether the result supports a correlogram is decided by
    ``correlogram``, so a single feature reads fine here.
    """
    points: list[tuple[float, float]] = []
    values: list[float] = []
    for feature in geojson["features"]:
        ring = feature["geometry"]["coordinates"][0][:-1]
        if not ring:
            raise ValueError("Grid feature has an empty ring")
        points.append((
            sum(corner[0] for corner in ring) / len(ring),
            sum(corner[1] for corner in ring) / len(ring),
        ))
        values.append(float(feature["properties"][field]))
    return points, values


def _to_metres(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Local equirectangular projection.

    The study area spans about 25 km, where the distortion is well under the
    precision this estimate claims.
    """
    mean_lat = sum(lat for _, lat in points) / len(points)
    lon_scale = METRES_PER_DEGREE_LON * math.cos(math.radians(mean_lat))
    return [(lon * lon_scale, lat * METRES_PER_DEGREE_LAT) for lon, lat in points]


def correlogram(
    points: list[tuple[float, float]],
    values: list[float],
    *,
    max_lag_m: float = 8000.0,
    bins: int = 40,
    min_pairs: int = 200,
) -> list[dict]:
    """Pearson correlation of the field within distance bands (a correlogram).

    Bands holding fewer than ``min_pairs`` grid pairs are dropped, so the tail
    of the curve is not driven by a handful of distant pairs.
    """
    if len(points) != len(values):
        raise ValueError("Points and values must have the same length")
    if len(points) < 3:
        raise ValueError("At least three grids are needed for a correlogram")
    if max_lag_m <= 0 or bins <= 0:
        raise ValueError("max_lag_m and bins must be positive")
    projected = _to_metres(points)
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    if variance == 0:
        raise ValueError("Field is constant, so it has no autocorrelation to measure")

    width = max_lag_m / bins
    pair_sum = [0.0] * bins
    pair_count = [0] * bins
    for i, (x_i, y_i) in enumerate(projected):
        deviation_i = values[i] - mean
        for j in range(i + 1, len(projected)):
            dx = x_i - projected[j][0]
            dy = y_i - projected[j][1]
            distance = math.sqrt(dx * dx + dy * dy)
            if distance < max_lag_m:
                slot = int(distance / width)
                pair_sum[slot] += deviation_i * (values[j] - mean)
                pair_count[slot] += 1

    entries = []
    for slot in range(bins):
        if pair_count[slot] >= min_pairs:
            entries.append({
                "lag_m": (slot + 0.5) * width,
                "correlation": (pair_sum[slot] / pair_count[slot]) / variance,
                "pairs": pair_count[slot],
            })
    if not entries:
        raise ValueError("No distance band held enough pairs; widen max_lag_m or lower min_pairs")
    return entries


def correlation_length(entries: list[dict], threshold: float = 0.5) -> float:
    """First distance where the correlation falls below ``threshold``.

    Interpolates between bands so the result is not quantised to the bin width.
    """
    if not -1 <= threshold <= 1:
        raise ValueError("threshold must lie between -1 and 1")
    previous: dict | None = None
    for entry in entries:
        if entry["correlation"] < threshold:
            if previous is None:
                return float(entry["lag_m"])
            span = previous["correlation"] - entry["correlation"]
            if span == 0:
                return float(entry["lag_m"])
            fraction = (previous["correlation"] - threshold) / span
            return previous["lag_m"] + fraction * (entry["lag_m"] - previous["lag_m"])
        previous = entry
    raise ValueError(f"Correlation never fell below {threshold} within the sampled distances")


def effective_sample_size(grid_count: int, grid_metres: float, length_m: float) -> float:
    """Order-of-magnitude independent sample count for a grid at ``length_m``.

    With correlation length L and spacing d, a field of independent patches
    holds roughly ``grid_count * (d / L) ** 2`` independent observations.
    """
    if length_m <= 0:
        raise ValueError("length_m must be positive")
    if grid_count <= 0 or grid_metres <= 0:
        raise ValueError("grid_count and grid_metres must be positive")
    return grid_count * (grid_metres / length_m) ** 2


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geojson", type=Path, default=Path("web/public/data/grids.geojson"))
    parser.add_argument("--field", default="lst_mean_c")
    parser.add_argument("--grid-metres", type=float, default=500.0)
    parser.add_argument("--max-lag-m", type=float, default=8000.0)
    parser.add_argument("--bins", type=int, default=40)
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()

    geojson = json.loads(args.geojson.read_text(encoding="utf-8"))
    points, values = centroids_and_values(geojson, args.field)
    entries = correlogram(points, values, max_lag_m=args.max_lag_m, bins=args.bins)
    length = correlation_length(entries, args.threshold)
    grid_count = len(points)
    effective = effective_sample_size(grid_count, args.grid_metres, length)

    print(f"field={args.field}  grids={grid_count}  spacing={args.grid_metres:g} m")
    print(f"{'lag_km':>7} {'correlation':>12} {'pairs':>8}")
    for entry in entries:
        print(f"{entry['lag_m'] / 1000:7.2f} {entry['correlation']:12.3f} {entry['pairs']:8d}")
    print()
    print(f"correlation length (r < {args.threshold:g}) = {length:.0f} m")
    print(f"effective sample size              ~ {effective:.0f}  (grids = {grid_count})")
    print("Order-of-magnitude estimate; not a substitute for a fitted variogram.")


if __name__ == "__main__":
    main()
