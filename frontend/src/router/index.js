import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'

const routes = [
  { path: '/', redirect: '/plan' },
  { path: '/login', component: () => import('../views/Login.vue') },
  { path: '/plan', component: () => import('../views/Home.vue') },
  { path: '/plaza', component: () => import('../views/Plaza.vue') },
  { path: '/center', component: () => import('../views/Center.vue') },

  // 管理员后台
  {
    path: '/admin',
    component: () => import('../views/admin/AdminLayout.vue'),
    children: [
      { path: '', redirect: '/admin/dashboard' },
      { path: 'dashboard', component: () => import('../views/admin/Dashboard.vue') },
      { path: 'users', component: () => import('../views/admin/UserManage.vue') },
      { path: 'cities', component: () => import('../views/admin/CityManage.vue') },
      { path: 'spots', component: () => import('../views/admin/SpotManage.vue') },
      { path: 'cost-matrix', component: () => import('../views/admin/CostManage.vue') },
      { path: 'plans', component: () => import('../views/admin/PlanManage.vue') },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const token = localStorage.getItem('token')

  // 登录页直接放行
  if (to.path === '/login') return true

  // 没有 token → 跳登录
  if (!token) {
    return { path: '/login' }
  }

  // admin 路由额外检查角色
  if (to.path.startsWith('/admin')) {
    const role = localStorage.getItem('user_role')
    if (role !== 'admin') {
      ElMessage.warning('无权限访问管理后台')
      return { path: '/plan' }
    }
  }
})

export default router
