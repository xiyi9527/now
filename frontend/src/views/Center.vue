<template>
  <div class="center">
    <header class="top-bar">
      <div class="brand">
        <el-icon size="22" color="#7c3aed"><Van /></el-icon>
        <span>智能旅行规划</span>
      </div>
      <nav class="nav">
        <router-link to="/plan" class="nav-item">🗺️ 规划</router-link>
        <router-link to="/plaza" class="nav-item">🌐 广场</router-link>
        <span class="nav-item active">👤 个人中心</span>
        <router-link v-if="isAdmin" to="/admin" class="nav-item admin-entry">🔐 管理后台</router-link>
      </nav>
      <div class="user-area">
        <el-tag effect="plain" round>Hi, {{ username }}</el-tag>
        <el-button size="small" link type="danger" @click="doLogout">退出</el-button>
      </div>
    </header>

    <main class="container">
      <!-- 用户卡片 -->
      <div class="user-hero">
        <div class="uh-left">
          <el-avatar :size="68" style="background:linear-gradient(135deg,#7c3aed,#ec4899);font-size:28px">
            {{ username.charAt(0).toUpperCase() }}
          </el-avatar>
          <div class="uh-info">
            <h2>{{ username }}</h2>
            <p>🛣️ 已规划 {{ plans.length }} 条路线 · ⭐ 收藏 {{ favorCount }} 条 · 🌐 分享 {{ publicCount }} 条</p>
          </div>
        </div>
        <div class="uh-btns">
          <el-button type="primary" @click="$router.push('/plan')">✨ 新规划</el-button>
          <el-button @click="$router.push('/plaza')">🌐 逛广场</el-button>
        </div>
      </div>

      <el-tabs v-model="tab" class="tabs">
        <el-tab-pane name="history">
          <template #label>
            <span class="tab-label">📋 历史规划 <el-badge v-if="plans.length" :value="plans.length" class="tab-badge" /></span>
          </template>
          <PlanGrid :plans="plans" :cityMap="cityMap" @open="showDetail" empty="还没有任何规划，去首页创建第一条吧 →" />
        </el-tab-pane>

        <el-tab-pane name="shared">
          <template #label>
            <span class="tab-label">🌐 已分享 <el-badge v-if="publicCount" :value="publicCount" class="tab-badge" type="success" /></span>
          </template>
          <PlanGrid :plans="plans.filter(p => p.is_public)" :cityMap="cityMap" @open="showDetail" empty="还没分享过规划" />
        </el-tab-pane>

        <el-tab-pane name="favorites">
          <template #label>
            <span class="tab-label">⭐ 收藏 <el-badge v-if="favorCount" :value="favorCount" class="tab-badge" type="warning" /></span>
          </template>
          <PlanGrid :plans="favorites" :cityMap="cityMap" @open="showDetail" empty="还没有收藏任何规划" />
        </el-tab-pane>
      </el-tabs>

      <!-- 详情抽屉 -->
      <el-drawer v-model="detailVisible" title="📋 规划详情" size="500px">
        <template v-if="detail">
          <div class="dp-route-card">
            <div class="drc-route">
              <span class="dp-city from">{{ cityName(detail.start_city_id) }}</span>
              <span class="dp-arrow">→</span>
              <span class="dp-city to">{{ cityName(detail.end_city_id) }}</span>
            </div>
            <div class="drc-meta">
              <el-tag v-if="detail.is_public" size="small" type="success">🌐 已公开</el-tag>
              <el-tag v-else size="small" type="info">🔒 私有</el-tag>
              <el-tag v-if="detail.spot_ids?.length" size="small" type="warning">🏞️ {{ detail.spot_ids.length }} 景点</el-tag>
            </div>
          </div>

          <el-descriptions :column="3" border class="dp-desc">
            <el-descriptions-item label="总时间">
              <strong class="val-time">{{ formatTime(detail.total_time) }}</strong>
            </el-descriptions-item>
            <el-descriptions-item label="总花费">
              <strong class="val-money">¥ {{ detail.total_money }}</strong>
            </el-descriptions-item>
            <el-descriptions-item label="体验">
              <strong class="val-dis">{{ detail.total_discomfort?.toFixed(1) || '-' }}</strong>
            </el-descriptions-item>
            <el-descriptions-item label="评分" :span="2">
              <el-rate :model-value="detail.rating || 0" disabled :max="5" />
            </el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ detail.created_at }}</el-descriptions-item>
          </el-descriptions>

          <h4 class="dp-step-title">📍 分步导航（{{ detail.route_detail?.steps?.length || 0 }} 步）</h4>
          <el-steps direction="vertical" :active="detail.route_detail?.steps?.length || 0" class="dp-steps">
            <el-step
              v-for="(s, i) in (detail.route_detail?.steps || [])"
              :key="i"
              :title="`${s.from_name} → ${s.to_name}`"
              :description="`${s.mode} · ${s.duration}min · ¥${s.cost}`"
              :status="s.mode === '景点游览' ? 'warning' : ''"
            />
          </el-steps>

          <div class="dp-actions">
            <el-button size="small" @click="toggleShare(detail)">
              {{ detail.is_public ? '🔒 改为私有' : '🌐 发布到广场' }}
            </el-button>
            <el-button size="small" type="warning" @click="toggleFav(detail)" v-if="detail.id">
              {{ isFavorited(detail.id) ? '⭐ 取消收藏' : '☆ 收藏' }}
            </el-button>
            <el-button size="small" type="primary" @click="replan(detail)">
              🚀 以此重新规划
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
import PlanGrid from '../components/PlanGrid.vue'
import {
  apiMyPlans, apiFavorites, apiAddFavorite, apiRemoveFavorite,
  apiSharePlan, apiUnsharePlan, apiCities,
} from '../api'

const router = useRouter()
const userStore = useUserStore()
const username = computed(() => userStore.username)
const isAdmin = computed(() => localStorage.getItem('user_role') === 'admin')
function doLogout() { userStore.logout(); router.push('/login') }

const tab = ref('history')
const plans = ref([])
const favorites = ref([])
const favIds = ref(new Set())
const cityMap = ref({})
const detailVisible = ref(false)
const detail = ref(null)

const favorCount = computed(() => favorites.value.length)
const publicCount = computed(() => plans.value.filter(p => p.is_public).length)

onMounted(async () => {
  const [d1, d2, d3] = await Promise.all([apiMyPlans(), apiFavorites(), apiCities()])
  plans.value = d1.data || []
  favorites.value = d2.data || []
  favIds.value = new Set(favorites.value.map(f => f.id))
  cityMap.value = Object.fromEntries((d3.data || []).map(c => [c.id, c.name]))
})

function cityName(id) { return cityMap.value[id] || ('#' + id) }
function formatTime(min) {
  const h = Math.floor(min / 60), m = min % 60
  return h ? `${h}h ${m}min` : `${m}min`
}
function showDetail(p) { detail.value = p; detailVisible.value = true }
function isFavorited(id) { return favIds.value.has(id) }

async function toggleShare(p) {
  try {
    if (p.is_public) await apiUnsharePlan(p.id)
    else await apiSharePlan(p.id)
    p.is_public = !p.is_public
    ElMessage.success(p.is_public ? '🌐 已发布到广场' : '🔒 已设为私有')
  } catch {}
}
async function toggleFav(p) {
  try {
    if (isFavorited(p.id)) {
      await apiRemoveFavorite(p.id); favIds.value.delete(p.id)
      ElMessage.success('已取消收藏')
    } else {
      await apiAddFavorite(p.id); favIds.value.add(p.id)
      ElMessage.success('⭐ 收藏成功')
    }
    favorites.value = (await apiFavorites()).data || []
  } catch {}
}
function replan(p) {
  sessionStorage.setItem('restore_plan', JSON.stringify({
    start_city_id: p.start_city_id,
    end_city_id: p.end_city_id,
    spot_ids: p.spot_ids,
  }))
  router.push('/plan')
}
</script>

<style scoped>
.center { min-height: 100vh; background: #f4f6fb; }
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
  color: #fff;
  font-weight: 600;
}
.nav-item.admin-entry:hover {
  background: linear-gradient(135deg, #b91c1c, #c2410c);
  color: #fff;
}
.container { max-width: 1100px; margin: 24px auto; padding: 0 20px; }

/* 用户卡片 */
.user-hero {
  background: linear-gradient(135deg, #7c3aed 0%, #ec4899 100%);
  border-radius: 16px; padding: 24px 28px;
  display: flex; justify-content: space-between; align-items: center;
  color: #fff; margin-bottom: 20px;
  box-shadow: 0 8px 24px rgba(124,58,237,0.25);
}
.uh-left { display: flex; gap: 18px; align-items: center; }
.uh-info h2 { margin: 0; font-size: 22px; }
.uh-info p { margin: 4px 0 0; font-size: 13px; opacity: 0.9; }
.uh-btns { display: flex; gap: 10px; }

/* Tab */
.tabs { background: #fff; border-radius: 14px; padding: 4px 16px; box-shadow: 0 2px 10px rgba(0,0,0,0.04); }
.tabs :deep(.el-tabs__item) { font-size: 15px; }
.tabs :deep(.el-tabs__active-bar) { background: linear-gradient(90deg, #7c3aed, #ec4899); height: 3px; }
.tab-label { display: inline-flex; align-items: center; gap: 6px; }
.tab-badge { margin-left: 2px; }

/* 抽屉内 */
.dp-route-card {
  background: linear-gradient(135deg, #f3e8ff, #fce7f3);
  border-radius: 12px; padding: 16px; margin-bottom: 16px;
}
.drc-route { display: flex; align-items: center; gap: 8px; font-size: 18px; font-weight: 700; }
.dp-city { padding: 4px 12px; border-radius: 8px; }
.dp-city.from { background: #d1fae5; color: #059669; }
.dp-city.to { background: #dbeafe; color: #2563eb; }
.dp-arrow { color: #7c3aed; }
.drc-meta { display: flex; gap: 8px; margin-top: 10px; }
.dp-desc { margin-bottom: 20px; }
.val-time { color: #2563eb; }
.val-money { color: #059669; }
.val-dis { color: #f59e0b; }
.dp-step-title { margin: 16px 0 12px; font-size: 15px; color: #374151; }
.dp-steps { padding: 8px 0; }
.dp-actions {
  margin-top: 20px; display: flex; gap: 10px; justify-content: flex-end; flex-wrap: wrap;
  padding-top: 16px; border-top: 1px solid #e5e7eb;
}
</style>
