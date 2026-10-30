/**
 * axios 封装
 * - 统一 baseURL（代理到 Flask 5000）
 * - 自动携带 JWT Authorization
 * - 统一错误处理
 */
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useUserStore } from '../stores/user'
import router from '../router'

const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  timeout: 60000,   // 算法计算可能比较久
})

service.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`
  }
  return config
})

service.interceptors.response.use(
  (resp) => resp,
  (err) => {
    // 401 / 422 都可能是 token 问题（Flask-JWT-Extended 4.6 格式错误返回 422）
    const s = err.response?.status
    if (s === 401 || s === 422) {
      const detail = err.response?.data?.msg || err.response?.data?.detail
      // 只有确实是 token/JWT 相关才清 token，否则不处理
      if (!detail || /token|jwt|unauthorized|signature|expired/i.test(String(detail))) {
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        if (router.currentRoute.value.path !== '/login') {
          ElMessage.warning('登录状态已失效，请重新登录')
          router.push('/login')
        }
        return Promise.reject(err)
      }
    }
    ElMessage.error(err.response?.data?.msg || err.message || '请求失败')
    return Promise.reject(err)
  }
)

export default service
