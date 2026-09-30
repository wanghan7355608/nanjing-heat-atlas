import type { GridCollection } from './types'

type Props = { data: GridCollection; selectedId: string | null; onSelect: (id: string) => void }

export function ScatterPlot({ data, selectedId, onSelect }: Props) {
  const width = 620, height = 280
  const left = 54, right = 18, top = 18, bottom = 42
  const points = data.features.map(feature => ({
    id: String(feature.id),
    x: feature.properties.ndvi_mean,
    y: feature.properties.lst_mean_c,
  }))
  const ymin = Math.floor(Math.min(...points.map(p => p.y)) / 5) * 5
  const ymax = Math.ceil(Math.max(...points.map(p => p.y)) / 5) * 5
  const xs = points.map(point => point.x)
  const xDataMin = Math.min(...xs)
  const xDataMax = Math.max(...xs)
  // Snap the axis to tenths of NDVI so the ticks read as round numbers.
  const xmin = Math.max(-1, Math.floor(xDataMin * 10) / 10)
  const xmax = Math.min(1, Math.ceil(xDataMax * 10) / 10)
  const xSpan = xmax - xmin || 1
  const plotWidth = width - left - right
  const plotHeight = height - top - bottom
  const xScale = (x: number) => left + ((x - xmin) / xSpan) * plotWidth
  const xTicks = Array.from({ length: 5 }, (_, index) => xmin + (xSpan * index) / 4)
  const yScale = (y: number) => top + ((ymax - y) / (ymax - ymin)) * plotHeight
  const xMean = points.reduce((sum, point) => sum + point.x, 0) / points.length
  const yMean = points.reduce((sum, point) => sum + point.y, 0) / points.length
  const covariance = points.reduce((sum, point) => sum + (point.x - xMean) * (point.y - yMean), 0)
  const variance = points.reduce((sum, point) => sum + (point.x - xMean) ** 2, 0)
  const slope = variance ? covariance / variance : 0
  const trendY = (x: number) => yMean + slope * (x - xMean)
  const selected = points.find(point => point.id === selectedId)

  return (
    <div className="scatter-wrap">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${points.length} 个网格的植被指数与地表温度散点图。`}>
        {[ymin, ymin + (ymax - ymin) / 2, ymax].map(value => (
          <g key={value}>
            <line x1={left} x2={width - right} y1={yScale(value)} y2={yScale(value)} className="chart-grid" />
            <text x={left - 9} y={yScale(value) + 4} textAnchor="end" className="chart-tick">{value.toFixed(0)}°</text>
          </g>
        ))}
        {xTicks.map((value, index) => (
          <text key={index} x={xScale(value)} y={height - 17} textAnchor="middle" className="chart-tick">{value.toFixed(2)}</text>
        ))}
        <line x1={left} x2={width - right} y1={height - bottom} y2={height - bottom} className="chart-axis" />
        <line x1={left} x2={left} y1={top} y2={height - bottom} className="chart-axis" />
        <line x1={xScale(xDataMin)} x2={xScale(xDataMax)} y1={yScale(trendY(xDataMin))} y2={yScale(trendY(xDataMax))} className="chart-trend" />
        {points.map(point => <circle key={point.id} cx={xScale(point.x)} cy={yScale(point.y)} r="2.35" className="chart-point" onClick={() => onSelect(point.id)} />)}
        {selected && <circle cx={xScale(selected.x)} cy={yScale(selected.y)} r="7" className="chart-selected" />}
      </svg>
      <div className="chart-axis-labels"><span>纵轴：地表温度（°C）</span><span>横轴：NDVI 植被指数</span></div>
    </div>
  )
}
