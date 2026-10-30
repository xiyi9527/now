/**
 * 用户状态（Pinia）
 */
import { defineStore } from 'pinia'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    user: JSON.parse(localStorage.getItem('user') || 'null'),
  }),
  getters: {
    isLogin: (state) => !!state.token,
    username: (state) => state.user?.username || '',
  },
  actions: {
    login(payload) {
      this.token = payload.access_token
      this.user = payload.user
      localStorage.setItem('token', payload.access_token)
      localStorage.setItem('user', JSON.stringify(payload.user))
      // 单独存一份 role，方便路由守卫快速读取
      localStorage.setItem('user_role', payload.user?.role || 'user')
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      localStorage.removeItem('user_role')
    },
  },
})
