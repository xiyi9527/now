/**
 * 管理员后台 API
 */
import request from '../utils/request'

// ---- stats ----
export const getStats = () => request.get('/admin/stats').then(r => r.data)

// 🆕 S4 dashboard
export const getDashboardOverview = () => request.get('/admin/dashboard/overview').then(r => r.data)
export const getHvConvergence = (plan_id) => request.get('/admin/dashboard/hv-convergence', { params: { plan_id } }).then(r => r.data)
export const getParetoScatter = (plan_id) => request.get('/admin/dashboard/pareto-scatter', { params: { plan_id } }).then(r => r.data)
export const getRecentPlans = (limit = 20) => request.get('/admin/dashboard/recent-plans', { params: { limit } }).then(r => r.data)
export const getAlgStats = () => request.get('/admin/dashboard/alg-stats').then(r => r.data)

// ---- users ----
export const getUsers = (params) => request.get('/admin/users', { params }).then(r => r.data)
export const updateUserRole = (uid, role) => request.put(`/admin/users/${uid}/role`, { role }).then(r => r.data)
export const deleteUser = (uid) => request.delete(`/admin/users/${uid}`).then(r => r.data)

// ---- cities ----
export const getCitiesAdmin = (params) => request.get('/admin/cities', { params }).then(r => r.data)
export const createCity = (data) => request.post('/admin/cities', data).then(r => r.data)
export const updateCity = (cid, data) => request.put(`/admin/cities/${cid}`, data).then(r => r.data)
export const deleteCity = (cid) => request.delete(`/admin/cities/${cid}`).then(r => r.data)

// ---- spots ----
export const getSpotsAdmin = (params) => request.get('/admin/spots', { params }).then(r => r.data)
export const createSpot = (data) => request.post('/admin/spots', data).then(r => r.data)
export const updateSpot = (sid, data) => request.put(`/admin/spots/${sid}`, data).then(r => r.data)
export const deleteSpot = (sid) => request.delete(`/admin/spots/${sid}`).then(r => r.data)

// ---- cost-matrix ----
export const getCostMatrix = (params) => request.get('/admin/cost-matrix', { params }).then(r => r.data)
export const createCostEntry = (data) => request.post('/admin/cost-matrix', data).then(r => r.data)
export const updateCostEntry = (mid, data) => request.put(`/admin/cost-matrix/${mid}`, data).then(r => r.data)
export const deleteCostEntry = (mid) => request.delete(`/admin/cost-matrix/${mid}`).then(r => r.data)
export const fillCostFromAmap = (data) => request.post('/admin/cost-matrix/fill-from-amap', data).then(r => r.data)

// ---- plans ----
export const getPlansAdmin = (params) => request.get('/admin/plans', { params }).then(r => r.data)
export const deletePlan = (pid) => request.delete(`/admin/plans/${pid}`).then(r => r.data)
