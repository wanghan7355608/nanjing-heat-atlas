import { useEffect, useRef } from 'react'
import maplibregl, { type Map as MapLibreMap } from 'maplibre-gl'
import type { FeatureCollection, LineString } from 'geojson'
import type { GridCollection, Metric } from './types'

type Props = {
  data: GridCollection
  bbox: [number, number, number, number]
  metric: Metric
  selectedId: string | null
  onSelect: (id: string) => void
}

const colors: Record<Metric, string[]> = {
  lst_mean_c: ['#2a788e', '#a9d6bd', '#f7dfa4', '#ef9a60', '#be4b3b'],
  ndvi_mean: ['#e7e5d8', '#c8dbb5', '#8abf8c', '#4d956e', '#1e6252'],
  green_share_pct: ['#e7e5d8', '#c8dbb5', '#8abf8c', '#4d956e', '#1e6252'],
  hot_share_pct: ['#f7efe3', '#f4cd9e', '#eba86a', '#d4703f', '#9c2f24'],
}

const breaks: Record<Metric, number[]> = {
  lst_mean_c: [35, 40, 45, 50, 55],
  ndvi_mean: [0, 0.2, 0.4, 0.6, 0.8],
  green_share_pct: [0, 25, 50, 75, 100],
  hot_share_pct: [0, 25, 50, 75, 100],
}

function fillExpression(metric: Metric): maplibregl.ExpressionSpecification {
  const b = breaks[metric]
  const c = colors[metric]
  return ['interpolate', ['linear'], ['get', metric], b[0], c[0], b[1], c[1], b[2], c[2], b[3], c[3], b[4], c[4]]
}

function makeGraticule(bbox: [number, number, number, number]): FeatureCollection<LineString> {
  const [west, south, east, north] = bbox
  const meridians = [118.7, 118.8, 118.9].filter(lon => lon > west && lon < east)
  const parallels = [32.0, 32.1, 32.2].filter(lat => lat > south && lat < north)
  return {
    type: 'FeatureCollection',
    features: [
      ...meridians.map(lon => ({ type: 'Feature' as const, properties: {}, geometry: { type: 'LineString' as const, coordinates: [[lon, south], [lon, north]] } })),
      ...parallels.map(lat => ({ type: 'Feature' as const, properties: {}, geometry: { type: 'LineString' as const, coordinates: [[west, lat], [east, lat]] } })),
    ],
  }
}

export function MapPanel({ data, bbox, metric, selectedId, onSelect }: Props) {
  const container = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const selectedRef = useRef<string | null>(selectedId)
  const onSelectRef = useRef(onSelect)

  useEffect(() => { selectedRef.current = selectedId }, [selectedId])
  useEffect(() => { onSelectRef.current = onSelect }, [onSelect])

  useEffect(() => {
    if (!container.current) return
    const map = new maplibregl.Map({
      container: container.current,
      style: {
        version: 8,
        sources: {},
        layers: [
          { id: 'background', type: 'background', paint: { 'background-color': '#e6ecea' } },
        ],
      },
      center: [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2],
      zoom: 10,
      minZoom: 9,
      maxZoom: 15,
      attributionControl: false,
    })
    mapRef.current = map
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
    map.on('load', () => {
      map.addSource('graticule', { type: 'geojson', data: makeGraticule(bbox) })
      map.addLayer({
        id: 'graticule', type: 'line', source: 'graticule',
        paint: { 'line-color': '#9dbab2', 'line-opacity': 0.65, 'line-width': 1, 'line-dasharray': [3, 4] },
      })
      map.addSource('grids', { type: 'geojson', data })
      map.addLayer({
        id: 'grid-fill', type: 'fill', source: 'grids',
        paint: { 'fill-color': fillExpression(metric), 'fill-opacity': 0.86 },
      })
      map.addLayer({
        id: 'grid-outline', type: 'line', source: 'grids',
        paint: { 'line-color': '#ffffff', 'line-opacity': 0.42, 'line-width': 0.45 },
      })
      map.addLayer({
        id: 'grid-selected', type: 'line', source: 'grids',
        filter: ['==', ['id'], selectedRef.current ?? '__none__'],
        paint: { 'line-color': '#102a37', 'line-width': 3 },
      })
      map.fitBounds([[bbox[0], bbox[1]], [bbox[2], bbox[3]]], { padding: 24, animate: false })
      map.on('mouseenter', 'grid-fill', () => { map.getCanvas().style.cursor = 'pointer' })
      map.on('mouseleave', 'grid-fill', () => { map.getCanvas().style.cursor = '' })
      map.on('click', 'grid-fill', (event) => {
        const id = event.features?.[0]?.id
        if (id !== undefined && id !== null) onSelectRef.current(String(id))
      })
    })
    return () => { map.remove(); mapRef.current = null }
    // The dataset and bounds are immutable after initial load.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, bbox])

  useEffect(() => {
    const map = mapRef.current
    if (map?.getLayer('grid-fill')) map.setPaintProperty('grid-fill', 'fill-color', fillExpression(metric))
  }, [metric])

  useEffect(() => {
    const map = mapRef.current
    if (map?.getLayer('grid-selected')) map.setFilter('grid-selected', ['==', ['id'], selectedId ?? '__none__'])
  }, [selectedId])

  return (
    <div className="map-wrap">
      <div ref={container} className="map-canvas" aria-label="南京热环境交互地图。点击网格查看详细数值。" />
      <div className="map-scale" aria-hidden="true"><span>低</span><div style={{ background: `linear-gradient(90deg, ${colors[metric].join(',')})` }} /><span>高</span></div>
      <p className="map-hint">离线经纬网 · 点击网格查看统计</p>
      <p className="coordinate-tag">{bbox[0].toFixed(2)}–{bbox[2].toFixed(2)}° E<br />{bbox[1].toFixed(2)}–{bbox[3].toFixed(2)}° N</p>
    </div>
  )
}
