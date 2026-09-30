import json
import math
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "web" / "public" / "data"


def test_committed_demo_data_matches_manifest_and_has_valid_values():
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    geojson = json.loads((DATA / "grids.geojson").read_text(encoding="utf-8"))
    features = geojson["features"]
    assert manifest["schema_version"] == 1
    assert manifest["item_id"] in manifest["source_item_url"]
    assert manifest["source_item_url"].startswith("https://planetarycomputer.microsoft.com/api/stac/v1/")
    assert geojson["type"] == "FeatureCollection"
    assert len(features) == manifest["summary"]["grid_count"] > 1000
    assert len({feature["id"] for feature in features}) == len(features)
    assert 60 <= manifest["valid_pixel_pct"] <= 100
    assert all(feature["geometry"]["coordinates"][0][0] == feature["geometry"]["coordinates"][0][-1] for feature in features)
    assert all(feature["properties"]["coverage_pct"] >= 60 for feature in features)
    assert all(0 <= feature["properties"]["green_share_pct"] <= 100 for feature in features)
    assert all(-1 <= feature["properties"]["ndvi_mean"] <= 1 for feature in features)
    assert all(math.isfinite(feature["properties"]["lst_mean_c"]) for feature in features)
    temperatures = np.array([feature["properties"]["lst_mean_c"] for feature in features])
    vegetation = np.array([feature["properties"]["ndvi_mean"] for feature in features])
    assert abs(float(np.corrcoef(vegetation, temperatures)[0, 1]) - manifest["summary"]["grid_ndvi_lst_correlation"]) < 0.002
