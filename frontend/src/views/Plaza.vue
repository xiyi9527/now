<template>
  <div class="plaza-page">
    <header class="top-bar">
      <div class="brand">
        <el-icon size="22" color="#7c3aed"><Van /></el-icon>
        <span>智能旅行规划</span>
      </div>
      <nav class="nav">
        <router-link to="/plan" class="nav-item">🗺️ 规划</router-link>
        <span class="nav-item active">🌐 广场</span>
        <router-link to="/center" class="nav-item">👤 个人中心</router-link>
        <router-link v-if="isAdmin" to="/admin" class="nav-item admin-entry">🔐 管理后台</router-link>
      </nav>
      <div class="user-area">
        <el-tag effect="plain" round>Hi, {{ username }}</el-tag>
        <el-button size="small" link type="danger" @click="doLogout">退出</el-button>
      </div>
    </header>

    <main class="container">
      <div class="hero">
        <div class="hero-left">
          <h2>🌐 旅行广场</h2>
          <p class="sub">看看大家都分享了哪些有意思的路线，点赞收藏你喜欢的方案</p>
        </div>
        <div class="hero-stats">
          <div class="hs-item"><strong>{{ routes.length }}</strong><span>分享路线</span></div>
          <div class="hs-item"><strong>{{ totalLikes }}</strong><span>累计点赞</span></div>
          <div class="hs-item"><strong>{{ totalFavs }}</strong><span>累计收藏</span></div>
        </div>
      </div>

      <div class="filter-bar">
        <el-radio-group v-model="sortTab" size="default" @change="loadRoutes">
          <el-radio-button value="recommend">✨ 推荐</el-radio-button>
          <el-radio-button value="latest">📅 最新</el-radio-button>
          <el-radio-button value="hot">🔥 热门</el-radio-button>
        </el-radio-group>
        <el-input
          v-model="keyword" placeholder="🔍 搜索路线..."
          class="search-input" clearable @keyup.enter="loadRoutes"
        >
          <template #append><el-button @click="loadRoutes">🔍</el-button></template>
        </el-input>
      </div>

      <el-empty v-if="!loading && routes.length === 0"
                description="暂无分享的路线，去规划一条分享吧 →">
        <el-button type="primary" @click="$router.push('/plan')">去规划</el-button>
      </el-empty>

      <div v-else class="plan-grid">
        <div v-for="r in routes" :key="r.id" class="plan-card" @click="showDetail(r)">
          <div class="pc-cover" :style="coverStyle(r)">
            <div class="pc-cover-grad"></div>
            <div class="pc-route-label">
              <span class="city-chip from">{{ r.origin_name || '起点' }}</span>
              <span class="arrow">→</span>
              <span class="city-chip to">{{ r.dest_name || '终点' }}</span>
            </div>
            <div class="pc-score" v-if="r.score">
              🔥 热度 {{ r.score }}
            </div>
          </div>
          <div class="pc-body">
            <h4 class="pc-title">{{ r.title }}</h4>
            <p class="pc-desc" v-if="r.description">{{ r.description }}</p>
            <div class="pc-stats">
              <div class="pc-stat">
                <span class="pcv like">👍 {{ r.likes || 0 }}</span>
                <span class="pcl">点赞</span>
              </div>
              <div class="pc-stat">
                <span class="pcv fav">⭐ {{ r.favorites_count || 0 }}</span>
                <span class="pcl">收藏</span>
              </div>
              <div class="pc-stat">
                <span class="pcv user">👤 {{ r.username || '匿名' }}</span>
                <span class="pcl">分享者</span>
              </div>
            </div>
            <div class="pc-foot">
              <span class="pc-time">📅 {{ fmtDate(r.created_at) }}</span>
              <div class="pc-actions" @click.stop>
                <el-button size="small" :type="likedMap[r.id] ? 'primary' : 'default'" @click="doLike(r)">
                  👍 {{ r.likes }}
                </el-button>
                <el-button size="small" :type="favMap[r.id] ? 'success' : 'default'" @click="doFav(r)">
                  ⭐ {{ r.favorites_count }}
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 详情抽屉 -->
      <el-drawer v-model="detailVisible" title="📋 路线详情" size="500px">
        <template v-if="detailRoute">
          <div class="dp-header">
            <div class="dp-route">
              <span class="dp-city from">{{ detailRoute.origin_name || '起点' }}</span>
              <span class="dp-arrow">→</span>
              <span class="dp-city to">{{ detailRoute.dest_name || '终点' }}</span>
            </div>
            <div class="dp-title">{{ detailRoute.title }}</div>
            <div class="dp-desc" v-if="detailRoute.description">{{ detailRoute.description }}</div>
          </div>

          <el-descriptions :column="3" border class="dp-desc" v-if="detailRoute.route_data">
            <el-descriptions-item label="总时间">
              <strong class="val-time">{{ formatTime(detailRoute.route_data.total_time || 0) }}</strong>
            </el-descriptions-item>
            <el-descriptions-item label="总花费">
              <strong class="val-money">¥ {{ detailRoute.route_data.total_money || 0 }}</strong>
            </el-descriptions-item>
            <el-descriptions-item label="体验分">
              <strong class="val-dis">{{ (detailRoute.route_data.total_discomfort || 0).toFixed(1) }}</strong>
            </el-descriptions-item>
          </el-descriptions>

          <h4 class="dp-step-title">📍 分步导航（{{ detailRoute.route_data?.steps?.length || 0 }} 步）</h4>
          <el-steps direction="vertical" :active="detailRoute.route_data?.steps?.length || 0" class="dp-steps">
            <el-step
              v-for="(s, i) in (detailRoute.route_data?.steps || [])"
              :key="i"
              :title="`${s.from_name || s.from || '起点'} → ${s.to_name || s.to || '终点'}`"
              :description="`${s.mode || ''} · ${s.duration || 0}min · ¥${s.cost || 0}`"
              :status="s.mode === '景点游览' ? 'warning' : ''"
            />
          </el-steps>

          <div class="dp-actions">
            <el-button @click.stop="doLike(detailRoute)" :type="likedMap[detailRoute.id] ? 'primary' : 'default'">
              👍 点赞 {{ detailRoute.likes }}
            </el-button>
            <el-button @click.stop="doFav(detailRoute)" :type="favMap[detailRoute.id] ? 'success' : 'default'">
              ⭐ 收藏 {{ detailRoute.favorites_count }}
            </el-button>
            <el-button type="primary" @click="doApply(detailRoute)">
              🚀 一键应用
            </el-button>
          </div>
        </template>
      </el-drawer>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '../stores/user'
import {
  apiPlazaList, apiPlazaDetail, apiPlazaLike,
  apiPlazaFavorite, apiPlazaFavCheck, apiPlazaApply,
} from '../api'

const router = useRouter()
const userStore = useUserStore()
const username = computed(() => userStore.username)
const isAdmin = computed(() => localStorage.getItem('user_role') === 'admin')
function doLogout() { userStore.logout(); router.push('/login') }

const routes = ref([])
const loading = ref(true)
const detailVisible = ref(false)
const detailRoute = ref(null)
const sortTab = ref('recommend')
const keyword = ref('')
const likedMap = ref({})     // { routeId: true }
const favMap = ref({})       // { routeId: true }

const totalLikes = computed(() => routes.value.reduce((s, r) => s + (r.likes || 0), 0))
const totalFavs = computed(() => routes.value.reduce((s, r) => s + (r.favorites_count || 0), 0))

async function loadRoutes() {
  loading.value = true
  try {
    const d = await apiPlazaList(sortTab.value, keyword.value.trim() || undefined)
    if (d.ok) routes.value = d.data || []
  } catch { ElMessage.error('加载广场失败') }
  finally { loading.value = false }
  // 批量查收藏状态
  if (userStore.isLogin && routes.value.length) {
    for (const r of routes.value) {
      try {
        const c = await apiPlazaFavCheck(r.id)
        if (c.ok) favMap.value[r.id] = c.data.favorited
      } catch {}
    }
  }
}

onMounted(loadRoutes)

function formatTime(min) {
  const h = Math.floor(min / 60), m = min % 60
  return h ? `${h}h ${m}min` : `${m}min`
}
function fmtDate(s) {
  if (!s) return ''
  return s.replace('T', ' ').slice(0, 16)
}

const gradients = [
  'linear-gradient(135deg,#7c3aed,#ec4899)',
  'linear-gradient(135deg,#0ea5e9,#6366f1)',
  'linear-gradient(135deg,#f97316,#e11d48)',
  'linear-gradient(135deg,#10b981,#0ea5e9)',
  'linear-gradient(135deg,#f59e0b,#ef4444)',
  'linear-gradient(135deg,#6366f1,#8b5cf6)',
]
function coverStyle(r) {
  const idx = (r.id * 7) % gradients.length
  return { background: gradients[idx] }
}

async function showDetail(r) {
  try {
    const d = await apiPlazaDetail(r.id)
    if (d.ok) detailRoute.value = d.data
  } catch { detailRoute.value = r }
  detailVisible.value = true
}

async function doLike(r) {
  try {
    const d = await apiPlazaLike(r.id)
    if (d.ok) {
      r.likes = d.likes
      likedMap.value[r.id] = true
      if (detailRoute.value?.id === r.id) detailRoute.value.likes = d.likes
    }
  } catch (e) { ElMessage.error('点赞失败，请先登录') }
}

async function doFav(r) {
  try {
    const d = await apiPlazaFavorite(r.id)
    if (d.ok) {
      r.favorites_count = d.favorites_count
      favMap.value[r.id] = d.favorited
      if (detailRoute.value?.id === r.id) detailRoute.value.favorites_count = d.favorites_count
      ElMessage.success(d.favorited ? '⭐ 已收藏' : '已取消收藏')
    }
  } catch (e) { ElMessage.error('收藏失败，请先登录') }
}

async function doApply(r) {
  try {
    const d = await apiPlazaApply(r.id)
    if (d.ok) {
      ElMessage.success('🚀 已应用到我的规划！')
      // 跳到个人中心
      router.push('/center')
    }
  } catch (e) { ElMessage.error('应用失败，请先登录') }
}
</script>

<style scoped>
.plaza-page { min-height: 100vh; background: #f4f6fb; }
.top-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 28px; background: #fff;
  box-shadow: 0 1px 6px rgba(0,0,0,0.05);
  position: sticky; top: 0; z-index: 100;
}
.brand { display: flex; align-items: center; gap: 8px; font-size: 17px; font-weight: 600; }
.nav { display: flex; gap: 4px; }
.nav-item {
  padding: 7px 15px; border-radius: 8px; color: #6b7280;
  text-decoration: none; font-size: 14px; cursor: pointer;
  transition: all 0.2s;
}
.nav-item:hover { background: #f3e8ff; color: #7c3aed; }
.nav-item.active { background: linear-gradient(135deg, #7c3aed, #a855f7); color: #fff; }
.nav-item.admin-entry {
  background: linear-gradient(135deg, #dc2626, #ea580c);
  color: #fff; font-weight: 600;
}
.nav-item.admin-entry:hover {
  background: linear-gradient(135deg, #b91c1c, #c2410c);
  color: #fff;
}
.container { max-width: 1200px; margin: 24px auto; padding: 0 20px; }

.hero {
  background: linear-gradient(135deg, #7c3aed 0%, #ec4899 100%);
  color: #fff; padding: 28px 32px; border-radius: 16px;
  display: flex; justify-content: space-between; align-items: center;
  box-shadow: 0 8px 24px rgba(124,58,237,0.25);
  margin-bottom: 20px;
}
.hero h2 { margin: 0 0 4px; font-size: 24px; }
.hero .sub { margin: 0; opacity: 0.9; font-size: 13px; }
.hero-stats { display: flex; gap: 24px; }
.hs-item { text-align: center; }
.hs-item strong { display: block; font-size: 22px; font-weight: 700; }
.hs-item span { font-size: 11px; opacity: 0.85; }

.filter-bar {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 18px; gap: 14px;
}
.search-input { width: 320px; }

.plan-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }
.plan-card {
  background: #fff; border-radius: 14px; overflow: hidden;
  cursor: pointer; border: 1px solid #e5e7eb;
  transition: all 0.3s;
}
.plan-card:hover {
  transform: translateY(-4px); box-shadow: 0 12px 32px rgba(124,58,237,0.18);
  border-color: #7c3aed;
}
.pc-cover {
  height: 120px; position: relative; overflow: hidden;
  display: flex; align-items: center; justify-content: center;
}
.pc-cover-grad {
  position: absolute; inset: 0;
  background: radial-gradient(circle at 30% 30%, rgba(255,255,255,0.25), transparent 60%);
}
.pc-route-label {
  position: relative; z-index: 2; display: flex; align-items: center; gap: 8px;
}
.city-chip {
  padding: 6px 14px; border-radius: 20px;
  background: rgba(255,255,255,0.95); color: #1f2937;
  font-weight: 600; font-size: 14px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}
.city-chip.from { color: #059669; }
.city-chip.to { color: #2563eb; }
.pc-route-label .arrow { font-size: 20px; color: #fff; font-weight: 700; }
.pc-score {
  position: absolute; top: 8px; right: 10px;
  color: #fff; font-size: 11px; font-weight: 600;
  background: rgba(255,255,255,0.25); padding: 3px 10px; border-radius: 10px;
  z-index: 2;
}

.pc-body { padding: 14px 16px; }
.pc-title { margin: 0 0 4px; font-size: 15px; color: #1f2937; }
.pc-desc { margin: 0 0 10px; font-size: 12px; color: #6b7280; line-height: 1.4;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.pc-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; margin-bottom: 10px; }
.pc-stat { text-align: center; }
.pcv { display: block; font-weight: 700; font-size: 15px; }
.pcv.like { color: #f59e0b; }
.pcv.fav { color: #ec4899; }
.pcv.user { color: #7c3aed; font-size: 12px; }
.pcl { font-size: 10px; color: #9ca3af; }
.pc-foot {
  display: flex; justify-content: space-between; align-items: center;
  font-size: 11px; color: #9ca3af;
}
.pc-actions { display: flex; gap: 6px; }

.dp-header {
  padding: 16px; background: linear-gradient(135deg, #f3e8ff, #fce7f3);
  border-radius: 12px; margin-bottom: 16px;
}
.dp-route { display: flex; align-items: center; gap: 8px; font-size: 18px; font-weight: 700; }
.dp-city { padding: 4px 12px; border-radius: 8px; }
.dp-city.from { background: #d1fae5; color: #059669; }
.dp-city.to { background: #dbeafe; color: #2563eb; }
.dp-arrow { color: #7c3aed; }
.dp-title { margin: 10px 0 4px; font-size: 17px; font-weight: 700; }
.dp-desc { margin: 0; font-size: 13px; color: #6b7280; line-height: 1.5; }
.dp-meta { display: flex; gap: 12px; margin-top: 10px; align-items: center; }
.dp-desc { margin-bottom: 20px; }
.val-time { color: #2563eb; }
.val-money { color: #059669; }
.val-dis { color: #f59e0b; }
.dp-step-title { margin: 16px 0 12px; font-size: 15px; color: #374151; }
.dp-steps { padding: 8px 0; }
.dp-actions {
  margin-top: 20px; display: flex; gap: 10px; justify-content: flex-end;
  padding-top: 16px; border-top: 1px solid #e5e7eb;
}
</style>
