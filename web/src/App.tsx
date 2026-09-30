import { useEffect, useMemo, useState } from 'react'
import { MapPanel } from './MapPanel'
import { ScatterPlot } from './ScatterPlot'
import type { GridCollection, GridFeature, Manifest, Metric } from './types'

const metricOptions: { key: Metric; label: string; unit: string; description: string }[] = [
  { key: 'lst_mean_c', label: '地表温度', unit: '°C', description: '每格有效像元的平均地表温度' },
  { key: 'ndvi_mean', label: '植被指数', unit: 'NDVI', description: '每格有效像元的平均植被指数' },
  { key: 'green_share_pct', label: '植被像元占比', unit: '%', description: 'NDVI ≥ 0.30 的有效像元比例' },
]

const base = import.meta.env.BASE_URL

function number(value: number, digits = 1) {
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value)
}

function dateInChina(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: 'long', day: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(new Date(value))
}

function dateOnlyInChina(value: string) {
  return new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: 'long', day: 'numeric' }).format(new Date(value))
}

export default function App() {
  const [data, setData] = useState<GridCollection | null>(null)
  const [manifest, setManifest] = useState<Manifest | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [metric, setMetric] = useState<Metric>('lst_mean_c')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([
      fetch(`${base}data/grids.geojson`).then(response => { if (!response.ok) throw new Error('网格数据加载失败'); return response.json() }),
      fetch(`${base}data/manifest.json`).then(response => { if (!response.ok) throw new Error('来源清单加载失败'); return response.json() }),
    ]).then(([grids, metadata]) => {
      if (!cancelled) { setData(grids as GridCollection); setManifest(metadata as Manifest) }
    }).catch((reason: unknown) => { if (!cancelled) setError(reason instanceof Error ? reason.message : '数据加载失败') })
    return () => { cancelled = true }
  }, [])

  const selected: GridFeature | undefined = useMemo(
    () => data?.features.find(feature => String(feature.id) === selectedId),
    [data, selectedId],
  )
  const extremes = useMemo(() => {
    if (!data?.features.length) return null
    return {
      hottest: data.features.reduce((a, b) => a.properties.lst_mean_c > b.properties.lst_mean_c ? a : b),
      greenest: data.features.reduce((a, b) => a.properties.green_share_pct > b.properties.green_share_pct ? a : b),
    }
  }, [data])
  const chosenMetric = metricOptions.find(option => option.key === metric)!

  return (
    <>
      <a className="skip-link" href="#main">跳转到主要内容</a>
      <header className="site-header">
        <div className="brand"><span className="brand-mark" aria-hidden="true">◒</span><div><strong>南京热环境图谱</strong><small>NANJING HEAT ATLAS</small></div></div>
        <nav aria-label="页面导航"><a href="#explore">数据探索</a><a href="#method">方法与边界</a><a href="#source">数据来源</a></nav>
        <span className="header-badge">GIS × 遥感 · 复试作品</span>
      </header>

      <main id="main">
        <section className="intro-shell" aria-labelledby="page-title">
          <div className="intro-copy">
            <p className="eyebrow"><span className="eyebrow-line" /> 从卫星影像到可解释的城市地图</p>
            <h1 id="page-title">南京的热，<br /><em>落在哪些地方？</em></h1>
            <p className="intro-description">一张真实影像，一套可复现的分析。探索南京主城区的地表温度与植被分布，并查看每个结论来自哪一景卫星数据。</p>
            <div className="intro-actions"><a className="button-primary" href="#explore">开始探索 <span aria-hidden="true">↗</span></a><a className="button-text" href="#method">了解计算方法 <span aria-hidden="true">→</span></a></div>
          </div>
          <div className="intro-visual" aria-hidden="true"><div className="orb orb-one" /><div className="orb orb-two" /><div className="orb orb-three" /><span className="visual-coordinate">32°N / 118°E</span><span className="visual-label">LAND SURFACE<br />TEMPERATURE</span></div>
        </section>

        {error && <div className="error-banner" role="alert">{error}。请确认 data 文件已生成，再刷新页面。</div>}
        {!error && (!data || !manifest) && <div className="loading" role="status">正在加载南京遥感分析数据…</div>}

        {data && manifest && <>
          <section className="metric-strip" aria-label="分析概览">
            <div className="metric-item"><span>卫星过境</span><strong>{dateInChina(manifest.acquired_at_utc)}</strong><small>{manifest.item_id.startsWith('LC09') ? 'Landsat 9' : 'Landsat 8'} · 单景观测</small></div>
            <div className="metric-item"><span>平均地表温度</span><strong>{number(manifest.summary.lst_mean_c)}<i>°C</i></strong><small>有效陆地像元均值</small></div>
            <div className="metric-item"><span>有效像元</span><strong>{number(manifest.valid_pixel_pct)}<i>%</i></strong><small>云、阴影与水体已剔除</small></div>
            <div className="metric-item"><span>可分析网格</span><strong>{manifest.summary.grid_count.toLocaleString('zh-CN')}</strong><small>{manifest.summary.grid_metres} 米 × {manifest.summary.grid_metres} 米</small></div>
          </section>

          <section id="explore" className="section-container explore-section" aria-labelledby="explore-title">
            <div className="section-heading"><div><p className="section-index">01 / INTERACTIVE ATLAS</p><h2 id="explore-title">把城市放进网格里看</h2><p>切换指标，点击任意网格查看局部数值。经纬网与分析图层都可离线显示。</p></div><span className="section-pill">真实 Landsat 数据</span></div>
            <div className="explore-layout">
              <div className="map-card">
                <div className="map-toolbar"><div><span className="toolbar-kicker">当前图层</span><strong>{chosenMetric.label}</strong><small>{chosenMetric.description}</small></div><div className="metric-switch" role="group" aria-label="地图指标">{metricOptions.map(option => <button key={option.key} type="button" aria-pressed={metric === option.key} onClick={() => setMetric(option.key)}>{option.label}</button>)}</div></div>
                <MapPanel data={data} bbox={manifest.bbox_wgs84} metric={metric} selectedId={selectedId} onSelect={setSelectedId} />
              </div>
              <aside className="insight-column" aria-label="网格详情和分析提示">
                <div className="insight-card dark-card"><span className="card-overline">GRID INSPECTOR</span><h3>{selected ? '选中网格' : '从地图选一个网格'}</h3>{selected ? <><p className="grid-id">{selected.id} · {selected.properties.valid_pixels} 个有效像元</p><div className="detail-main">{number(selected.properties.lst_mean_c)}<span>°C</span></div><p className="detail-caption">卫星过境时的平均地表温度</p><div className="detail-rows"><div><span>平均 NDVI</span><strong>{number(selected.properties.ndvi_mean, 3)}</strong></div><div><span>植被像元占比</span><strong>{number(selected.properties.green_share_pct)}%</strong></div><div><span>有效覆盖</span><strong>{number(selected.properties.coverage_pct)}%</strong></div></div></> : <p className="empty-detail">网格的颜色展示总体分布。点选后可查看具体温度、植被指数与有效覆盖率。</p>}</div>
                <div className="insight-card quick-card"><span className="card-overline">QUICK LOOK</span><h3>试着看两个极端</h3><button type="button" onClick={() => extremes && setSelectedId(String(extremes.hottest.id))}>定位最热网格 <span aria-hidden="true">↗</span></button><button type="button" onClick={() => extremes && setSelectedId(String(extremes.greenest.id))}>定位植被最多网格 <span aria-hidden="true">↗</span></button></div>
                <div className="insight-note"><span aria-hidden="true">◎</span><p>地表温度不是体感温度，也不是 2 米气温。这里只描述一次卫星过境时的空间差异。</p></div>
              </aside>
            </div>
          </section>

          <section className="section-container relationship-section" aria-labelledby="relationship-title"><div className="section-heading"><div><p className="section-index">02 / SPATIAL RELATIONSHIP</p><h2 id="relationship-title">植被多的地方，更凉吗？</h2><p>每个点代表一个符合覆盖门槛的 500 米网格。趋势线展示样区内的描述性关系。</p></div></div><div className="relationship-layout"><div className="chart-card"><ScatterPlot data={data} selectedId={selectedId} onSelect={setSelectedId} /></div><div className="correlation-card"><span className="card-overline">GRID-LEVEL CORRELATION</span><strong>{manifest.summary.grid_ndvi_lst_correlation === null ? '—' : number(manifest.summary.grid_ndvi_lst_correlation, 3)}</strong><p>NDVI 与地表温度的网格相关系数</p><div className="correlation-rule" /><small>负相关表示本景影像中，植被指数较高的网格通常更凉。地形、建筑密度和其他因素也会影响温度；这个结果不能证明绿地造成了降温。</small></div></div></section>

          <section id="method" className="section-container method-section" aria-labelledby="method-title"><div className="section-heading"><div><p className="section-index">03 / METHOD & LIMITS</p><h2 id="method-title">结论是怎样算出来的</h2><p>计算步骤公开，关键筛选条件与未覆盖的范围也公开。</p></div></div><div className="method-grid"><article><span>01</span><h3>读影像</h3><p>从 Planetary Computer STAC 定位 Landsat 8/9 Collection 2 Level-2 场景，按南京样区读取 COG 窗口。</p></article><article><span>02</span><h3>清理像元</h3><p>用 QA_PIXEL 排除填充值、云、云影、雪和水体；把热红外波段换算为摄氏度，红光与近红外计算 NDVI。</p></article><article><span>03</span><h3>聚合与检查</h3><p>按 UTM 50N 建立 500 米网格，要求至少 60% 有效覆盖；计算温度、NDVI、植被占比和描述性相关系数。</p></article></div><div className="limitation-box"><strong>解释边界</strong><p>仅反映 {dateOnlyInChina(manifest.acquired_at_utc)} 一次过境；无法代表全年或长期趋势。云掩膜与 30 米分辨率会影响细节，网格相关性不等于因果关系。</p></div></section>

          <section id="source" className="section-container source-section" aria-labelledby="source-title"><div><p className="section-index">04 / SOURCE & REPRODUCIBILITY</p><h2 id="source-title">每一个数字都可追溯</h2><p>影像标识、生成参数和网格结果都随项目公开。可以从同一景影像重新运行数据管线。</p></div><div className="source-card"><div><span>影像 ID</span><code>{manifest.item_id}</code></div><div><span>场景云量</span><strong>{number(manifest.scene_cloud_cover_pct, 2)}%</strong></div><div><span>分析投影</span><strong>{manifest.crs}</strong></div><div className="source-links"><a href={manifest.source_item_url} target="_blank" rel="noreferrer">查看原始 STAC 条目 ↗</a><a href={`${base}data/manifest.json`} download>下载来源清单 ↓</a><a href={`${base}data/grids.geojson`} download>下载网格数据 ↓</a></div></div></section>
        </>}
      </main>
      <footer className="site-footer"><strong>南京热环境图谱</strong><span>用真实数据，讲清楚一座城市的空间差异。</span><small>遥感数据：USGS Landsat / Microsoft Planetary Computer · 经纬网：本项目生成</small></footer>
    </>
  )
}
