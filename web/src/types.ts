import type { Feature, FeatureCollection, Polygon } from 'geojson'

export interface GridProperties {
  lst_mean_c: number
  ndvi_mean: number
  green_share_pct: number
  hot_share_pct: number
  coverage_pct: number
  valid_pixels: number
}

export type GridFeature = Feature<Polygon, GridProperties>
export type GridCollection = FeatureCollection<Polygon, GridProperties>
export type Metric = 'lst_mean_c' | 'ndvi_mean' | 'green_share_pct'

export interface Manifest {
  schema_version: number
  generated_at_utc: string
  title: string
  area: string
  bbox_wgs84: [number, number, number, number]
  crs: string
  item_id: string
  acquired_at_utc: string
  scene_cloud_cover_pct: number
  source_item_url: string
  source_collection_url: string
  source_assets: Record<string, string>
  valid_pixels: number
  sampled_pixels: number
  valid_pixel_pct: number
  summary: {
    grid_count: number
    grid_metres: number
    lst_mean_c: number
    lst_p10_c: number
    lst_p90_c: number
    hot_threshold_c: number
    ndvi_mean: number
    grid_ndvi_lst_correlation: number | null
  }
}
