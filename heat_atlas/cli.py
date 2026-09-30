"""Build the public demo dataset from a real Landsat scene."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from . import __version__
from .analysis import QA_REJECT_BITS, aggregate_grid, calculate_indices, valid_pixel_mask
from .sources import ASSETS, COLLECTION, STAC_BASE, fetch_item, read_bands


DEFAULT_ITEM = "LC08_L2SP_120038_20240809_02_T1"
DEFAULT_BBOX = (118.68, 31.99, 118.95, 32.22)


def build_dataset(item_id: str, bbox: tuple[float, float, float, float], grid_metres: int) -> tuple[dict, dict]:
    west, south, east, north = bbox
    if not (west < east and south < north and -180 <= west <= 180 and -180 <= east <= 180 and -90 <= south <= 90 and -90 <= north <= 90):
        raise ValueError("Invalid WGS84 bounding box")
    item = fetch_item(item_id)
    bands, transform, crs = read_bands(item, bbox)
    mask = valid_pixel_mask(bands["qa_pixel"], bands["lwir11"], bands["red"], bands["nir08"])
    lst_c, ndvi = calculate_indices(bands["lwir11"], bands["red"], bands["nir08"])
    result = aggregate_grid(lst_c, ndvi, mask, transform, crs, grid_metres=grid_metres)
    source_url = f"{STAC_BASE}/collections/{COLLECTION}/items/{item_id}"
    manifest = {
        "schema_version": 1,
        "pipeline_version": __version__,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "title": "南京城市热环境与绿地分析",
        "area": "南京主城区样区",
        "bbox_wgs84": list(bbox),
        "crs": str(crs),
        "item_id": item_id,
        "acquired_at_utc": item["properties"]["datetime"],
        "scene_cloud_cover_pct": item["properties"].get("eo:cloud_cover"),
        "source_item_url": source_url,
        "source_collection_url": f"{STAC_BASE}/collections/{COLLECTION}",
        "source_assets": {name: item["assets"][name]["title"] for name in ASSETS},
        "qa_reject_bits": list(QA_REJECT_BITS),
        "green_ndvi_threshold": 0.30,
        "min_grid_coverage": 0.60,
        "valid_pixels": result.valid_pixels,
        "sampled_pixels": result.total_pixels,
        "valid_pixel_pct": round(result.valid_pixels / result.total_pixels * 100, 1),
        "summary": result.summary,
        "notes": [
            "LST is land surface temperature at the satellite overpass, not near-surface air temperature.",
            "Grid-level NDVI/LST correlation is descriptive, not evidence of causal cooling.",
            "Cloud, shadow, snow and water pixels are excluded; grids require at least 60% valid coverage.",
        ],
    }
    geojson = {"type": "FeatureCollection", "features": result.features}
    return geojson, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--item-id", default=DEFAULT_ITEM)
    parser.add_argument("--bbox", nargs=4, type=float, metavar=("WEST", "SOUTH", "EAST", "NORTH"), default=DEFAULT_BBOX)
    parser.add_argument("--grid-metres", type=int, default=500)
    parser.add_argument("--output", type=Path, default=Path("web/public/data"))
    args = parser.parse_args()
    print(f"Reading Landsat item {args.item_id} for {tuple(args.bbox)}")
    geojson, manifest = build_dataset(args.item_id, tuple(args.bbox), args.grid_metres)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "grids.geojson").write_text(json.dumps(geojson, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (args.output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Exported {manifest['summary']['grid_count']} grids; {manifest['valid_pixel_pct']}% valid source pixels")


if __name__ == "__main__":
    main()
