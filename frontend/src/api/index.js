/**
 * 后端 API 调用（代理到 /api/*）
 */
import http from '../utils/request'

// ---- 认证 ----
export const apiRegister = (data) => http.post('/register', data).then(r => r.data)
export const apiLogin = (data) => http.post('/login', data).then(r => r.data)

// ---- 基础数据 ----
export const apiCities = () => http.get('/cities').then(r => r.data)
export const apiSpots = (cityId) =>
  http.get('/spots', { params: { city_id: cityId } }).then(r => r.data)

// ---- 🔍 统一搜索（城市 + 景点 + 高德 POI 补全） ----
export const apiSearch = (q, limit = 20) =>
  http.get('/search', { params: { q, limit } }).then(r => r.data)

// ---- 附近景点推荐 ----
export const apiSpotsRecommend = (startCityId, endCityId, radiusKm = 300) =>
  http.get('/spots/recommend', {
    params: {
      start_city_id: startCityId,
      end_city_id: endCityId,
      radius_km: radiusKm,
    },
  }).then(r => r.data)

// ---- 核心规划 ----
export const apiPlan = (payload) =>
  http.post('/plan', payload).then(r => r.data)

// ---- 保存 / 我的 / 广场 ----
export const apiSavePlan = (data) =>
  http.post('/plan/save', data).then(r => r.data)
export const apiMyPlans = () => http.get('/plan/me').then(r => r.data)
export const apiPublicPlans = () => http.get('/plan/public').then(r => r.data)

// ---- 评分 ----
export const apiRatePlan = (planId, rating) =>
  http.post(`/plan/${planId}/rate`, { rating }).then(r => r.data)

// ---- 分享 ----
export const apiSharePlan = (planId) =>
  http.post(`/plan/${planId}/share`).then(r => r.data)
export const apiUnsharePlan = (planId) =>
  http.post(`/plan/${planId}/unshare`).then(r => r.data)

// ---- 收藏 ----
export const apiFavorites = () => http.get('/favorites').then(r => r.data)
export const apiAddFavorite = (planId) =>
  http.post('/favorites', { plan_id: planId }).then(r => r.data)
export const apiRemoveFavorite = (planId) =>
  http.delete(`/favorites/${planId}`).then(r => r.data)
export const apiCheckFavorite = (planId) =>
  http.get(`/favorites/check/${planId}`).then(r => r.data)

// 🆕 S5: 出行提示
export const apiTipMatch = (cities, category) =>
  http.get('/tip/match', { params: { cities, category } }).then(r => r.data)
export const apiTipRecommend = (city, limit = 5) =>
  http.get('/tip/recommend', { params: { city, limit } }).then(r => r.data)

// 🆕 S6: 交通方式打分闭环
export const apiSubmitRate = (plan_id, mode, score, comment) =>
  http.post('/rate', { plan_id, mode, score, comment }).then(r => r.data)
export const apiUserMeans = () => http.get('/rate/user-means').then(r => r.data)
export const apiPlanRatings = (planId) => http.get(`/rate/plan/${planId}`).then(r => r.data)

// 🆕 S7: 路线广场增强
export const apiPlazaShare = (data) => http.post('/plaza/share', data).then(r => r.data)
export const apiPlazaList = (sort, q) => http.get('/plaza/list', { params: { sort, q } }).then(r => r.data)
export const apiPlazaDetail = (sid) => http.get(`/plaza/${sid}`).then(r => r.data)
export const apiPlazaLike = (sid) => http.post(`/plaza/${sid}/like`).then(r => r.data)
export const apiPlazaFavorite = (sid) => http.post(`/plaza/${sid}/favorite`).then(r => r.data)
export const apiPlazaFavCheck = (sid) => http.get(`/plaza/favorites/check/${sid}`).then(r => r.data)
export const apiPlazaApply = (sid) => http.post(`/plaza/${sid}/apply`).then(r => r.data)
