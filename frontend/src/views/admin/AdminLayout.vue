<template>
  <el-container class="admin-layout">
    <!-- 左侧侧边栏 -->
    <el-aside :width="collapse ? '64px' : '220px'" class="aside">
      <div class="logo-area" :class="{ collapsed: collapse }">
        <span class="logo-icon">🧭</span>
        <span v-if="!collapse" class="logo-text">Admin</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        :collapse="collapse"
        :collapse-transition="false"
        background-color="#001529"
        text-color="#b7bdc6"
        active-text-color="#fff"
        router
        class="admin-menu"
      >
        <el-menu-item index="/admin/dashboard">
          <span class="menu-icon">📊</span>
          <template #title>仪表盘</template>
        </el-menu-item>
        <el-menu-item index="/admin/users">
          <span class="menu-icon">👥</span>
          <template #title>用户管理</template>
        </el-menu-item>
        <el-menu-item index="/admin/cities">
          <span class="menu-icon">🏙️</span>
          <template #title>城市管理</template>
        </el-menu-item>
        <el-menu-item index="/admin/spots">
          <span class="menu-icon">🏞️</span>
          <template #title>景点管理</template>
        </el-menu-item>
        <el-menu-item index="/admin/cost-matrix">
          <span class="menu-icon">💰</span>
          <template #title>成本矩阵</template>
        </el-menu-item>
        <el-menu-item index="/admin/plans">
          <span class="menu-icon">🗺️</span>
          <template #title>规划记录</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <!-- 顶部栏 -->
      <el-header class="header">
        <div class="header-left">
          <el-icon class="collapse-btn" :size="20" @click="collapse = !collapse">
            <Fold v-if="!collapse" />
            <Expand v-else />
          </el-icon>
          <span class="header-title">智能旅行规划 · 管理后台</span>
        </div>
        <div class="header-right">
          <el-tag effect="plain" round type="success">
            Hi, {{ username }}
          </el-tag>
          <el-button size="small" type="danger" link @click="handleLogout">退出</el-button>
        </div>
      </el-header>

      <!-- 主内容区 -->
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Fold, Expand } from '@element-plus/icons-vue'
import { useUserStore } from '../../stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const collapse = ref(false)
const username = computed(() => userStore.username || 'Admin')

const activeMenu = computed(() => {
  // 把 /admin 重定向也指向 dashboard
  if (route.path === '/admin') return '/admin/dashboard'
  return route.path
})

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    userStore.logout()
    // 同时清掉 user_role
    localStorage.removeItem('user_role')
    ElMessage.success('已退出登录')
    router.push('/login')
  } catch {
    // 用户取消
  }
}
</script>

<style scoped>
.admin-layout {
  height: 100vh;
}

/* 侧边栏 */
.aside {
  background-color: #001529;
  transition: width 0.2s;
  overflow: hidden;
}

.logo-area {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #fff;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 2px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  white-space: nowrap;
}
.logo-area.collapsed .logo-icon {
  font-size: 22px;
}
.logo-icon {
  font-size: 22px;
}
.logo-text {
  background: linear-gradient(135deg, #7c3aed, #ec4899);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.admin-menu {
  border-right: none;
}
.admin-menu .el-menu-item {
  height: 52px;
  line-height: 52px;
  border-bottom: none;
}
.menu-icon {
  display: inline-block;
  margin-right: 8px;
}
.admin-menu .el-menu-item.is-active {
  background-color: #1890ff !important;
  color: #fff !important;
}

/* 顶部栏 */
.header {
  background: #fff;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  height: 60px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.collapse-btn {
  cursor: pointer;
  color: #555;
  transition: color 0.2s;
}
.collapse-btn:hover {
  color: #1890ff;
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* 主区域 */
.main {
  background: #f0f2f5;
  padding: 20px;
  overflow-y: auto;
}
</style>
