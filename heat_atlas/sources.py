"""Planetary Computer STAC and Landsat COG readers.

Signed URLs are ephemeral and intentionally never written to disk or logs.
"""

from __future__ import annotations

from urllib.parse import urlparse

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.windows import Window, from_bounds
import requests


STAC_BASE = "https://planetarycomputer.microsoft.com/api/stac/v1"
SIGN_ENDPOINT = "https://planetarycomputer.microsoft.com/api/sas/v1/sign"
COLLECTION = "landsat-c2-l2"
ASSETS = ("lwir11", "red", "nir08", "qa_pixel")


def fetch_item(item_id: str) -> dict:
    url = f"{STAC_BASE}/collections/{COLLECTION}/items/{item_id}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    item = response.json()
    missing = set(ASSETS) - set(item.get("assets", {}))
    if missing:
        raise ValueError(f"STAC item missing assets: {', '.join(sorted(missing))}")
    return item


def _signed_href(href: str) -> str:
    response = requests.get(SIGN_ENDPOINT, params={"href": href}, timeout=30)
    response.raise_for_status()
    signed = response.json()["href"]
    if urlparse(signed).scheme != "https":
        raise ValueError("Signing service returned a non-HTTPS asset URL")
    return signed


def _window_for_bbox(dataset, bbox: tuple[float, float, float, float]) -> Window:
    west, south, east, north = bbox
    transformer = Transformer.from_crs("EPSG:4326", dataset.crs, always_xy=True)
    corners = [transformer.transform(lon, lat) for lon in (west, east) for lat in (south, north)]
    left = min(point[0] for point in corners)
    right = max(point[0] for point in corners)
    bottom = min(point[1] for point in corners)
    top = max(point[1] for point in corners)
    requested = from_bounds(left, bottom, right, top, dataset.transform).round_offsets().round_lengths()
    full = Window(0, 0, dataset.width, dataset.height)
    try:
        window = requested.intersection(full)
    except rasterio.errors.WindowError as exc:
        raise ValueError("Requested bounding box does not intersect the Landsat image") from exc
    if window.width < 2 or window.height < 2:
        raise ValueError("Requested bounding box is too small")
    return window


def read_bands(item: dict, bbox: tuple[float, float, float, float]) -> tuple[dict[str, np.ndarray], object, object]:
    """Read aligned COG windows for the requested WGS84 bounding box."""
    bands: dict[str, np.ndarray] = {}
    transform = None
    crs = None
    reference = None
    with rasterio.Env(
        GDAL_DISABLE_READDIR_ON_OPEN="YES",
        CPL_VSIL_CURL_USE_HEAD="NO",
        GDAL_HTTP_MAX_RETRY="3",
        GDAL_HTTP_RETRY_DELAY="2",
    ):
        for name in ASSETS:
            href = _signed_href(item["assets"][name]["href"])
            try:
                with rasterio.open(href) as dataset:
                    if reference is None:
                        reference = (dataset.width, dataset.height, dataset.transform, dataset.crs)
                        window = _window_for_bbox(dataset, bbox)
                        transform = dataset.window_transform(window)
                        crs = dataset.crs
                    elif (dataset.width, dataset.height, dataset.transform, dataset.crs) != reference:
                        raise ValueError(f"Landsat asset {name} is not aligned with the thermal asset")
                    bands[name] = dataset.read(1, window=window)
            except rasterio.errors.RasterioIOError:
                # Rasterio errors can contain the SAS URL. Never expose it.
                raise RuntimeError(f"Remote COG read failed for Landsat asset {name}") from None
    return bands, transform, crs
