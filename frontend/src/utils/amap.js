/**
 * 高德地图 SDK 懒加载封装
 * 使用 @amap/amap-jsapi-loader 统一加载 AMap / AMap.Scale / AMap.ToolBar 等插件
 */
import AMapLoader from '@amap/amap-jsapi-loader'

let _AMap = null
let _loadingPromise = null

export function loadAMap() {
  if (_AMap) return Promise.resolve(_AMap)
  if (_loadingPromise) return _loadingPromise

  const key = import.meta.env.VITE_AMAP_KEY || '5a7e58b1a1234567890abcdefg'

  _loadingPromise = AMapLoader.load({
    key,
    version: '2.0',
    plugins: ['AMap.Scale', 'AMap.ToolBar', 'AMap.Marker'],
  }).then((AMap) => {
    _AMap = AMap
    return AMap
  }).catch((e) => {
    console.error('高德地图加载失败', e)
    _loadingPromise = null
    throw e
  })

  return _loadingPromise
}

/** 安全地初始化地图实例（避免 AMap 被 Vue 响应式包装出 bug —— 经验教训 1118152） */
export function createMap(container, opts = {}) {
  if (!_AMap) throw new Error('AMap 未加载，请先 await loadAMap()')
  return new _AMap.Map(container, {
    zoom: 5,
    center: [116.397428, 39.90923],
    viewMode: '2D',
    ...opts,
  })
}
