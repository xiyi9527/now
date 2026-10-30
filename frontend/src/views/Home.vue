<template>
  <div class="home">
    <!-- 顶部导航 -->
    <header class="top-bar">
      <div class="brand">
        <el-icon size="22" color="#7c3aed"><Van /></el-icon>
        <span>智能旅行规划</span>
      </div>
      <nav class="nav">
        <span class="nav-item active">🗺️ 规划</span>
        <router-link to="/plaza" class="nav-item">🌐 广场</router-link>
        <router-link to="/center" class="nav-item">👤 个人中心</router-link>
        <router-link v-if="isAdmin" to="/admin" class="nav-item admin-entry">🔐 管理后台</router-link>
      </nav>
      <div class="user-area">
        <el-tag effect="plain" round>Hi, {{ username }}</el-tag>
        <el-button size="small" link type="danger" @click="doLogout">退出</el-button>
      </div>
    </header>

    <main class="main" :class="{ 'has-results': plans.length > 0 }">
      <!-- 左侧：搜索 + 景点推荐 + 附近景点 -->
      <aside class="left-panel">
        <!-- ========== 搜索 Hero ========== -->
        <section class="hero">
          <h1 class="hero-title">🎒 出去玩玩</h1>
          <p class="hero-sub">选好起点终点，帮你规划最优路线</p>

          <div class="search-row">
            <!-- 起点 -->
            <div class="search-item">
              <div class="search-label">🚩 出发</div>
              <el-autocomplete
                v-model="startInput"
                :fetch-suggestions="(q, cb) => handleSearch(q, cb, 'start')"
                placeholder="搜城市 / 景点 或 自动定位"
                class="city-select" size="large"
                popper-class="search-dropdown"
                clearable
                :trigger-on-focus="true"
                @select="(item) => handleSelect(item, 'start')"
              >
                <template #default="{ item }">
                  <!-- 分组 header -->
                  <div v-if="item.isSectionHeader" class="dropdown-section">{{ item.label }}</div>
                  <!-- 正常项 -->
                  <div v-else class="search-item-row" :class="'row-' + item.type">
                    <div class="row-left">
                      <span class="row-icon">{{ item.type === 'spot' ? '📍' : item.type === 'poi' ? '🔍' : item.type === '__auto__' ? '🎯' : '🏙️' }}</span>
                      <span class="search-item-label" v-html="highlight(item.name || item.label, item._q)"></span>
                    </div>
                    <span v-if="item.address" class="search-item-addr">{{ item.address }}</span>
                  </div>
                </template>
                <template #prefix>
                  <el-icon size="16" color="#fff"><Search /></el-icon>
                </template>
              </el-autocomplete>
            </div>

            <div class="swap-btn" @click="swapCities">
              <el-icon :size="20"><Sort /></el-icon>
            </div>

            <!-- 终点 -->
            <div class="search-item">
              <div class="search-label">🏁 目的</div>
              <el-autocomplete
                v-model="endInput"
                :fetch-suggestions="(q, cb) => handleSearch(q, cb, 'end')"
                placeholder="想去哪里？搜城市 / 景点 / POI"
                class="city-select" size="large"
                popper-class="search-dropdown"
                clearable
                :trigger-on-focus="true"
                @select="(item) => handleSelect(item, 'end')"
              >
                <template #default="{ item }">
                  <div v-if="item.isSectionHeader" class="dropdown-section">{{ item.label }}</div>
                  <div v-else class="search-item-row" :class="'row-' + item.type">
                    <div class="row-left">
                      <span class="row-icon">{{ item.type === 'spot' ? '📍' : item.type === 'poi' ? '🔍' : item.type === '__auto__' ? '🎯' : '🏙️' }}</span>
                      <span class="search-item-label" v-html="highlight(item.name || item.label, item._q)"></span>
                    </div>
                    <span v-if="item.address" class="search-item-addr">{{ item.address }}</span>
                  </div>
                </template>
                <template #prefix>
                  <el-icon size="16" color="#fff"><Location /></el-icon>
                </template>
              </el-autocomplete>
            </div>
          </div>

          <div class="opt-row">
            <!-- 🆕 S9: 交通方式偏好（偏好→方案→导航全链路一致） -->
            <el-radio-group v-model="transportMode" size="small" class="mode-group">
              <el-radio-button value="auto">🤖 智能</el-radio-button>
              <el-radio-button value="driving">🚗 自驾</el-radio-button>
            </el-radio-group>
            <el-button size="small" @click="showSpotModal = true" :disabled="!startCityId || !endCityId">
              🎯 选择途经景点
              <el-tag v-if="selectedSpotIds.length" class="ml-1" size="small" type="warning">
                {{ selectedSpotIds.length }}
              </el-tag>
            </el-button>
          </div>

          <button
            class="plan-btn"
            :disabled="!startCityId || !endCityId || planning"
            @click="doPlan"
          >
            <el-icon v-if="!planning"><Promotion /></el-icon>
            {{ planning ? '🧠 NSGA-II 算法计算中...' : '✨ 开始智能规划' }}
          </button>
        </section>

        <!-- ========== 景点推荐 ========== -->
        <section class="rec-section">
          <div class="sec-head">
            <h3>🔥 热门景点 <span class="sec-count">共 {{ spots.length }} 个</span></h3>
            <span class="sec-sub">点击看详情 · 小按钮快速加入</span>
          </div>
          <div class="rec-grid">
            <div
              v-for="s in pagedSpots" :key="s.id" class="spot-card"
              :class="{ selected: selectedSpotIds.includes(s.id) }"
              @click="openSpotDetail(s)"
            >
              <div class="spot-img">
                <img :src="s.img_url" :alt="s.name" @error="(e) => e.target.style.display='none'" />
                <div class="spot-overlay">
                  <span class="spot-city">{{ s.city_name }}</span>
                </div>
                <div class="spot-quick-btn"
                     :class="{ selected: selectedSpotIds.includes(s.id) }"
                     @click.stop="toggleSpotQuick(s)">
                  {{ selectedSpotIds.includes(s.id) ? '✓' : '＋' }}
                </div>
              </div>
              <div class="spot-info">
                <h4>{{ s.name }}</h4>
                <p>{{ s.description }}</p>
              </div>
            </div>
          </div>
          <!-- 🆕 底部分页器 -->
          <div v-if="spots.length > spotPageSize" class="rec-pager">
            <el-pagination
              v-model:current-page="spotPage"
              :page-size="spotPageSize"
              :total="spots.length"
              layout="total, prev, pager, next, jumper"
              background
              small
            />
          </div>
        </section>
      </aside>

      <!-- 右侧：只在有规划结果时才出现（动态 grid 切到两栏） -->
      <section v-if="plans.length" class="right-panel">
        <div class="result-section">
          <div class="res-head">
            <h3>🎯 找到 {{ plans.length }} 种方案</h3>
            <el-radio-group v-model="sortTab" size="small">
              <el-radio-button value="recommend">✨ 推荐</el-radio-button>
              <el-radio-button value="fastest">⏱ 最快</el-radio-button>
              <el-radio-button value="cheapest">💰 最少</el-radio-button>
              <el-radio-button value="best">🌟 最佳</el-radio-button>
            </el-radio-group>
          </div>

          <div class="plan-scroll">
            <div
              v-for="(opt, idx) in sortedPlans"
              :key="idx"
              class="plan-card"
              :class="{ active: idx === activeIdx }"
              @click="selectPlan(idx)"
            >
              <div class="plan-head">
                <el-tag v-if="idx === 0" type="warning" size="small">推荐</el-tag>
                <span class="plan-title">方案 #{{ idx + 1 }}</span>
                <span class="plan-tag" v-if="opt.spot_ids.length">🏞️ 含景点</span>
              </div>
              <div class="plan-stats">
                <div class="stat">
                  <span class="val">{{ formatTime(opt.total_time) }}</span>
                  <span class="lab">总时间</span>
                </div>
                <div class="stat">
                  <span class="val">¥{{ opt.total_money }}</span>
                  <span class="lab">总花费</span>
                </div>
                <div class="stat">
                  <span class="val dis">{{ opt.total_discomfort.toFixed(1) }}</span>
                  <span class="lab">不适感</span>
                </div>
              </div>
              <div class="plan-actions">
                <el-button size="small" @click.stop="selectPlan(idx)">🗺️ 查看路线</el-button>
                <el-button size="small" type="success" @click.stop="savePlan(opt)">💾 保存</el-button>
              </div>
            </div>
          </div>

          <!-- 🆕 S5: 出行提示卡（按途经城市匹配） -->
          <div v-if="tipGroups && (tipGroups.安顺?.length || tipGroups.宜宾?.length || tipGroups.全国?.length)" class="tip-section">
            <h4>💡 出行提示</h4>
            <div class="tip-grid">
              <template v-for="(tips, city) in tipGroups" :key="city">
                <div v-if="tips.length" class="tip-city-block">
                  <div class="tip-city-head">📍 {{ city }}</div>
                  <div v-for="t in tips" :key="t.id" class="tip-card" :class="`cat-${t.category}`">
                    <div class="tip-cat">{{ tipCatLabel(t.category) }}</div>
                    <div class="tip-title">{{ t.title }}</div>
                    <div class="tip-content">{{ t.content }}</div>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </div>
      </section>
    </main>

    <!-- ========== 附近景点弹窗 ========== -->
    <el-dialog v-model="showSpotModal" title="🎯 选择途经景点" width="720px" destroy-on-close>
      <div v-if="!recSpots.start_near?.length && !recSpots.end_near?.length && !recSpots.line_near?.length"
           class="no-rec">
        <el-icon :size="40" color="#d1d5db"><Location /></el-icon>
        <p>起点或终点城市信息不足，无法推荐附近景点</p>
      </div>

      <template v-else>
        <el-tabs v-model="spotTab">
          <el-tab-pane :label="`🚩 起点附近 (${recSpots.start_near?.length || 0})`" name="start">
            <div class="spot-popup-grid">
              <div v-for="s in recSpots.start_near" :key="s.id"
                   class="spot-popup-item" @click="toggleSpotModal(s)">
                <img :src="s.img_url" />
                <div class="spi-info">
                  <h4>{{ s.name }}</h4>
                  <p>{{ s.description }}</p>
                  <el-tag size="small">{{ s.distance_km }}km</el-tag>
                </div>
                <div class="spi-check">{{ selectedSpotIds.includes(s.id) ? '✓ 已选' : '＋' }}</div>
              </div>
            </div>
          </el-tab-pane>
          <el-tab-pane :label="`🏁 终点附近 (${recSpots.end_near?.length || 0})`" name="end">
            <div class="spot-popup-grid">
              <div v-for="s in recSpots.end_near" :key="s.id"
                   class="spot-popup-item" @click="toggleSpotModal(s)">
                <img :src="s.img_url" />
                <div class="spi-info">
                  <h4>{{ s.name }}</h4>
                  <p>{{ s.description }}</p>
                  <el-tag size="small">{{ s.distance_km }}km</el-tag>
                </div>
                <div class="spi-check">{{ selectedSpotIds.includes(s.id) ? '✓ 已选' : '＋' }}</div>
              </div>
            </div>
          </el-tab-pane>
          <el-tab-pane :label="`📐 直线附近 (${recSpots.line_near?.length || 0})`" name="line">
            <div class="spot-popup-grid">
              <div v-for="s in recSpots.line_near" :key="s.id"
                   class="spot-popup-item" @click="toggleSpotModal(s)">
                <img :src="s.img_url" />
                <div class="spi-info">
                  <h4>{{ s.name }}</h4>
                  <p>{{ s.description }}</p>
                  <el-tag size="small">距路线 {{ s.distance_km }}km</el-tag>
                </div>
                <div class="spi-check">{{ selectedSpotIds.includes(s.id) ? '✓ 已选' : '＋' }}</div>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
        <div class="modal-footer">
          <span>已选 {{ selectedSpotIds.length }} 个景点</span>
          <el-button type="primary" @click="showSpotModal = false">确定</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- ========== 景点详情弹窗 ========== -->
    <el-dialog v-model="showSpotDetail" :title="null" width="560px" destroy-on-close
               class="spot-detail-dialog" :show-close="false">
      <div v-if="activeSpot" class="spot-detail">
        <div class="sd-img">
          <img :src="activeSpot.img_url" :alt="activeSpot.name" @error="(e) => e.target.style.opacity='0.3'" />
          <div class="sd-img-grad"></div>
          <button class="sd-close" @click="showSpotDetail=false">×</button>
          <h2 class="sd-title">{{ activeSpot.name }}</h2>
          <div class="sd-meta">
            <el-tag size="small" type="success">📍 {{ activeSpot.city_name }}</el-tag>
            <span class="sd-coord">
              经 {{ Number(activeSpot.lng).toFixed(3) }} · 纬 {{ Number(activeSpot.lat).toFixed(3) }}
            </span>
          </div>
        </div>
        <div class="sd-body">
          <h4>📖 景点介绍</h4>
          <p>{{ activeSpot.description || '暂无描述' }}</p>
          <div class="sd-info-row">
            <div class="sd-info-cell">
              <span class="sd-info-val">~{{ activeSpot.cost_time_extra || 120 }} min</span>
              <span class="sd-info-lab">建议游览时长</span>
            </div>
            <div class="sd-info-cell">
              <span class="sd-info-val">🏞️</span>
              <span class="sd-info-lab">热门景点</span>
            </div>
          </div>
        </div>
        <div class="sd-actions">
          <el-button @click="showSpotDetail=false">取消</el-button>
          <el-button type="warning" @click="
            startInput = activeSpot.name; startName = activeSpot.name;
            startLat = activeSpot.lat; startLng = activeSpot.lng;
            startCityId = activeSpot.city_id; startSpotId = activeSpot.id;
            showSpotDetail = false;
            ElMessage.success('🚩 已设为起点');
          ">🚩 设为起点</el-button>
          <el-button type="success" @click="
            endInput = activeSpot.name; endName = activeSpot.name;
            endLat = activeSpot.lat; endLng = activeSpot.lng;
            endCityId = activeSpot.city_id; endSpotId = activeSpot.id;
            showSpotDetail = false;
            ElMessage.success('🏁 已设为终点');
          ">🏁 设为终点</el-button>
          <el-button
            :type="selectedSpotIds.includes(activeSpot.id) ? 'default' : 'primary'"
            @click="toggleActiveSpot(); showSpotDetail=false">
            {{ selectedSpotIds.includes(activeSpot.id) ? '✓ 已加入（点击移除）' : '＋ 加入规划' }}
          </el-button>
        </div>
      </div>
    </el-dialog>

    <!-- ========== 分步抽屉（详情 + 大地图） ========== -->
    <el-drawer v-model="drawerVisible" title="🗺️ 路线详情 & 分步导航" size="520px">
      <div v-if="activePlan" class="drawer-content">

        <!-- 地图：抽屉打开时才懒加载 -->
        <div class="drawer-map-wrap">
          <div v-if="!mapReady" class="drawer-map-loading">
            <el-icon class="is-loading" :size="28"><Loading /></el-icon>
            <span>加载地图中…</span>
          </div>
          <div v-show="mapReady" ref="mapRef" class="drawer-map"></div>
        </div>

        <div class="plan-summary">
          <div class="sum-row">
            <div><b>{{ cityName(startCityId) }}</b> → <b>{{ cityName(endCityId) }}</b></div>
            <el-rate v-model="userRating" :max="5" size="small" @change="submitRating" />
          </div>
          <div class="sum-stats">
            <div><strong>{{ formatTime(activePlan.total_time) }}</strong><span>总时间</span></div>
            <div><strong>¥{{ activePlan.total_money }}</strong><span>总花费</span></div>
            <div><strong>{{ activePlan.total_discomfort.toFixed(1) }}</strong><span>不适感</span></div>
          </div>
        </div>

        <div class="current-step">
          📍 当前：{{ currentStepPreview }}
        </div>

        <!-- 🆕 估算方案时间轴（飞机/高铁/大巴等无真实导航的方案） -->
        <div v-if="activePlan.is_estimated && activePlan.display_steps?.length" class="est-timeline">
          <div class="est-banner">
            <el-tag size="small" type="warning" effect="dark">估算方案</el-tag>
            <span class="est-banner-text">路线/距离/时间为估算，地图显示为直线</span>
          </div>
          <div class="est-spine">
            <div v-for="(ds, i) in activePlan.display_steps" :key="i" class="est-row">
              <!-- 起点/终点圆 -->
              <div v-if="ds.type === 'origin' || ds.type === 'destination'" class="est-circle"
                   :class="ds.type === 'origin' ? 'est-origin' : 'est-dest'">
                {{ ds.marker }}
              </div>
              <div v-if="ds.type === 'origin' || ds.type === 'destination'" class="est-label">
                <div class="est-name">{{ ds.name }}</div>
                <div class="est-coord">{{ ds.lng.toFixed(4) }}, {{ ds.lat.toFixed(4) }}</div>
              </div>
              <!-- 交通段标签（仿图片高德样式） -->
              <div v-if="ds.type === 'transit'" class="est-transit">
                <div class="est-mode-pill" :class="`mode-${ds.mode}`">{{ ds.mode }}</div>
                <div class="est-transit-info">
                  <span class="est-time">{{ ds.time_str }}</span>
                  <span class="est-money">{{ ds.money_str }}</span>
                  <span class="est-dist">· {{ ds.dist_str }}</span>
                  <span v-if="ds.n_transfers" class="est-transfer">· 换乘 {{ ds.n_transfers }} 次</span>
                </div>
                <div class="est-note">{{ ds.note }}</div>
              </div>
            </div>
          </div>
        </div>

        <el-steps direction="vertical" :active="currentStepIdx" class="steps">
          <el-step
            v-for="(s, i) in activePlan.steps" :key="i"
            :title="s.from_name + ' → ' + s.to_name"
            :description="s.mode + ' · ' + s.duration + 'min · ¥' + s.cost"
            :status="s.mode === '景点游览' ? 'warning' : ''"
            :disabled="i > currentStepIdx"
          />
        </el-steps>

        <!-- 🆕 高德逐步导航指令（可折叠） -->
        <el-collapse v-if="currentStep?.amap_steps?.length" class="amap-nav" accordion>
          <el-collapse-item name="nav" class="amap-nav-item">
            <template #title>
              <span class="nav-title">
                🗺️ 高德逐步导航（{{ currentStep.amap_steps.length }} 条指令）
                <el-tag size="small" type="success" effect="plain">实时</el-tag>
              </span>
            </template>
            <div class="nav-instructions">
              <div
                v-for="(ins, i) in currentStep.amap_steps"
                :key="i"
                class="nav-row"
                :title="ins.road ? `途经 ${ins.road}` : ''"
              >
                <span class="nav-num">{{ i + 1 }}</span>
                <span class="nav-text">{{ ins.instruction }}</span>
                <span class="nav-meta">
                  <span v-if="ins.road" class="nav-road">📍 {{ ins.road }}</span>
                  <span class="nav-dist">{{ ins.distance_str }}</span>
                  <span class="nav-dur">{{ ins.duration_str }}</span>
                </span>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>

        <!-- 🆕 S6: 交通方式打分（使用-打分-优化闭环） -->
        <div v-if="activePlan._plan_id && planModes.length" class="rate-section">
          <div class="rate-head">
            <span>⭐ 给交通方式打分</span>
            <el-tag size="small" type="info">影响下次规划</el-tag>
          </div>
          <div class="rate-hint">打分反馈到 NSGA-II 体验惩罚：+2 喜欢降惩罚，-2 不喜欢加惩罚</div>
          <div v-for="mode in planModes" :key="mode" class="rate-row">
            <span class="rate-mode">{{ mode }}</span>
            <el-radio-group v-model="ratingScores[mode]" size="small">
              <el-radio-button v-for="s in [-2,-1,0,1,2]" :key="s" :value="s">{{ s > 0 ? '+' + s : s }}</el-radio-button>
            </el-radio-group>
            <el-button size="small" type="primary" @click="submitModeRate(mode)">提交</el-button>
          </div>
        </div>

        <div class="drawer-actions">
          <div class="step-info">第 {{ currentStepIdx + 1 }} / {{ activePlan.steps.length }} 步</div>
          <div class="step-btns">
            <el-button @click="prevStep" :disabled="currentStepIdx === 0" size="small">⬅ 上步</el-button>
            <el-button type="primary" @click="nextStep"
              :disabled="currentStepIdx >= activePlan.steps.length - 1" size="small">
              ✓ {{ currentStepIdx >= activePlan.steps.length - 1 ? '完成' : '下一步' }}
            </el-button>
          </div>
          <div class="action-btns">
            <el-button size="small" @click="backToHero">⬅ 返回修改</el-button>
            <el-button type="success" size="small" @click="savePlan(activePlan)">💾 保存</el-button>
            <el-button size="small" type="warning" @click="shareToPlaza" v-if="activePlan._plan_id">
              🌐 分享到广场
            </el-button>
          </div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '../stores/user'
import {
  apiCities, apiSpots, apiPlan, apiSpotsRecommend, apiSearch,
  apiSavePlan, apiRatePlan, apiCheckFavorite, apiTipMatch,
  apiSubmitRate, apiUserMeans, apiPlazaShare,
} from '../api'
import { loadAMap, createMap } from '../utils/amap'

const router = useRouter()
const userStore = useUserStore()
const username = computed(() => userStore.username)
const isAdmin = computed(() => localStorage.getItem('user_role') === 'admin')
function doLogout() { userStore.logout(); router.push('/login') }

// ========== 数据 ==========
const cities = ref([])
const spots = ref([])
// 🆕 首页景点分页
const spotPage = ref(1)
const spotPageSize = ref(8)
const pagedSpots = computed(() => {
  const start = (spotPage.value - 1) * spotPageSize.value
  return spots.value.slice(start, start + spotPageSize.value)
})
const startCityId = ref(null)
const endCityId = ref(null)
const startSpotId = ref(null)    // 🔍 用户选了 spot 作为起点时记录
const endSpotId = ref(null)      // 🔍 用户选了 spot 作为终点时记录
const startLat = ref(null); const startLng = ref(null); const startName = ref(null)   // 起点真实坐标
const endLat = ref(null);   const endLng = ref(null);   const endName = ref(null)     // 终点真实坐标
const startInput = ref('')   // 出发搜索框文本
const endInput = ref('')     // 目的搜索框文本
const selectedSpotIds = ref([])
const transportMode = ref('driving')   // 🆕 交通方式: driving / transit / walking / auto
const planning = ref(false)
const sortTab = ref('recommend')
const showSpotModal = ref(false)
const spotTab = ref('start')
const tipGroups = ref({})   // 🆕 S5: 出行提示分组
const recSpots = reactive({ start_near: [], end_near: [], line_near: [] })
const showSpotDetail = ref(false)
const activeSpot = ref(null)
function openSpotDetail(s) { activeSpot.value = s; showSpotDetail.value = true }
function toggleActiveSpot() { if (activeSpot.value) toggleSpotQuick(activeSpot.value) }
function spotCityId() { return activeSpot.value?.city_id }

function cityName(id) {
  const c = cities.value.find(x => x.id === id)
  return c?.name || ('#' + id)
}
function swapCities() {
  const a = startCityId.value; startCityId.value = endCityId.value; endCityId.value = a
  const ai = startInput.value; startInput.value = endInput.value; endInput.value = ai
}

// ========== 🔍 搜索辅助 ==========
/** 关键字高亮：把 text 里 q 子串用 <mark> 包裹 */
function highlight(text, q) {
  if (!q) return text
  const safe = String(text || '')
  const re = new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi')
  return safe.replace(re, m => `<mark>${m}</mark>`)
}

/** 分组 header 构造器（el-autocomplete 会把它当普通 option，所以 handleSelect 里要跳过） */
const _H = (label) => ({ isSectionHeader: true, value: label, label })

// ========== 🔍 统一搜索（debounce + 分组 + 关键字高亮） ==========
let _searchTimer = null
let _searchCache = new Map()

function handleSearch(query, callback, which) {
  const q = (query || '').trim()
  clearTimeout(_searchTimer)

  // --- 空查询：简单下拉候选（热门城市+景点） ---
  if (!q) {
    const hotCities = cities.value.filter(c => c.is_hot).slice(0, 12)
    const recSpots = spots.value.slice(0, 8)
    const list = [
      _H('🎯 快速入口'),
      { value: '📍 自动定位', label: '📍 自动定位', address: '使用浏览器定位当前位置', type: '__auto__', name: '自动定位' },
      _H('🏙️ 热门城市'),
      ...hotCities.map(c => ({
        value: c.name, label: c.name + (c.is_hot ? ' 🔥' : ''), address: c.province || '',
        type: 'city', city_id: c.id, lat: c.lat, lng: c.lng, name: c.name,
      })),
      _H('📍 热门景点'),
      ...recSpots.map(s => ({
        value: s.name, label: s.name, address: cityName(s.city_id),
        type: 'spot', spot_id: s.id, city_id: s.city_id, lat: s.lat, lng: s.lng, name: s.name,
      })),
    ]
    callback(list)
    return
  }

  // --- 有查询：先缓存直接用 ---
  if (_searchCache.has(q)) { callback(_searchCache.get(q)); return }

  _searchTimer = setTimeout(async () => {
    try {
      const d = await apiSearch(q)
      const raw = d.data || []
      // 按 match 字段分三组
      const exact = raw.filter(x => x.match === 'exact')
      const fuzzy = raw.filter(x => x.match === 'fuzzy')
      const amap  = raw.filter(x => x.match === 'amap')
      // 组装带分组 header + _q 高亮标记的列表
      const list = []
      if (exact.length || fuzzy.length) {
        list.push(_H('✅ 本地匹配'))
        for (const x of exact) list.push({ ...x, value: x.label, _q: q })
        for (const x of fuzzy) list.push({ ...x, value: x.label, _q: q })
      }
      if (amap.length) {
        list.push(_H('🔍 高德 POI'))
        for (const x of amap) list.push({ ...x, value: x.label, _q: q })
      }
      _searchCache.set(q, list)
      if (_searchCache.size > 200) _searchCache.clear()
      callback(list)
    } catch {
      callback([])
    }
  }, 200)
}

function _haversineKm(lat1, lng1, lat2, lng2) {
  const R = 6371.0
  const p1 = lat1 * Math.PI / 180, p2 = lat2 * Math.PI / 180
  const dp = (lat2 - lat1) * Math.PI / 180
  const dl = (lng2 - lng1) * Math.PI / 180
  const a = Math.sin(dp/2)**2 + Math.cos(p1)*Math.cos(p2)*Math.sin(dl/2)**2
  return 2 * R * Math.asin(Math.sqrt(a))
}

// 高德 POI → 找最近的已知城市
function _nearestCityId(lat, lng) {
  if (!cities.value.length) return null
  let best = null, bestD = Infinity
  for (const c of cities.value) {
    const d = _haversineKm(lat, lng, c.lat, c.lng)
    if (d < bestD) { bestD = d; best = c }
  }
  return best ? { city: best, km: bestD } : null
}

function handleSelect(item, which) {
  if (!item || item.isSectionHeader) return   // 跳过分组 header
  if (item.type === '__auto__') {
    doLocate(which)
    return
  }

  // 🎯 全部类型都记录真实经纬度和名称（给后端 plan_direct_by_coords 用）
  const lat = item.lat; const lng = item.lng; const name = item.name || item.label?.replace(/^[^\u4e00-\u9fff]+/, '')
  if (which === 'start') { startLat.value = lat; startLng.value = lng; startName.value = name }
  else                  { endLat.value   = lat;   endLng.value   = lng;   endName.value   = name }

  if (item.type === 'city') {
    if (which === 'start') { startCityId.value = item.city_id; startSpotId.value = null }
    else { endCityId.value = item.city_id; endSpotId.value = null }
  } else if (item.type === 'spot') {
    if (which === 'start') { startCityId.value = item.city_id; startSpotId.value = item.spot_id }
    else                   { endCityId.value   = item.city_id; endSpotId.value   = item.spot_id }
    // ✅ 修复：起点/终点就是起点/终点，不再自动加入途经景点
    // 途经景点只能由用户主动在热门景点 / 沿途推荐里点 ➕ 加入
    ElMessage.info(`📍 设为${which === 'start' ? '起点' : '终点'}：${item.name}`)
  } else if (item.type === 'poi') {
    const near = _nearestCityId(item.lat, item.lng)
    if (near) {
      if (which === 'start') startCityId.value = near.city.id
      else endCityId.value = near.city.id
      // 🔧 不再只显示"最近城市"提示，也说明真实经纬度已传给后端
      ElMessage.info(`📍 ${item.name}（${item.lat.toFixed(3)}, ${item.lng.toFixed(3)}）`)
    } else {
      ElMessage.warning('未找到匹配的城市')
    }
  }
}

// ========== 自动定位 ==========
const locating = ref(false)
function doLocate(which = 'start') {
  if (!navigator.geolocation) {
    ElMessage.warning('当前浏览器不支持定位')
    return
  }
  locating.value = true
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const lat = pos.coords.latitude, lng = pos.coords.longitude
      locating.value = false
      const hit = _nearestCityId(lat, lng)
      if (hit) {
        if (which === 'start') {
          startCityId.value = hit.city.id
          startInput.value = hit.city.name
          // 🆕 设经纬度+名称（让 plan_direct_by_coords 可用，不再只设 cityId）
          startLat.value = lat
          startLng.value = lng
          startName.value = `我的位置(${lat.toFixed(4)},${lng.toFixed(4)})`
        } else {
          endCityId.value = hit.city.id
          endInput.value = hit.city.name
          endLat.value = lat
          endLng.value = lng
          endName.value = `我的位置(${lat.toFixed(4)},${lng.toFixed(4)})`
        }
        ElMessage.success(`📍 已定位到「${hit.city.name}」(距 ${hit.km.toFixed(0)}km)，坐标已设好可直接规划`)
      } else {
        // 🆕 附近没城市也允许用真实坐标规划
        if (which === 'start') {
          startLat.value = lat
          startLng.value = lng
          startName.value = `我的位置(${lat.toFixed(4)},${lng.toFixed(4)})`
          startInput.value = startName.value
        } else {
          endLat.value = lat
          endLng.value = lng
          endName.value = `我的位置(${lat.toFixed(4)},${lng.toFixed(4)})`
          endInput.value = endName.value
        }
        ElMessage.success(`📍 已定位，坐标已设好可直接规划`)
      }
    },
    (err) => {
      locating.value = false
      ElMessage.warning('定位失败: ' + err.message)
    },
    { enableHighAccuracy: true, timeout: 8000 }
  )
}
function toggleSpotQuick(s) {
  if (selectedSpotIds.value.includes(s.id)) selectedSpotIds.value = selectedSpotIds.value.filter(x => x !== s.id)
  else selectedSpotIds.value.push(s.id)
}
function removeSpot(sid) { selectedSpotIds.value = selectedSpotIds.value.filter(x => x !== sid) }
function toggleSpotModal(s) {
  if (selectedSpotIds.value.includes(s.id)) selectedSpotIds.value = selectedSpotIds.value.filter(x => x !== s.id)
  else selectedSpotIds.value.push(s.id)
}
async function openSpotModal() {
  if (!startCityId.value || !endCityId.value) return
  const d = await apiSpotsRecommend(startCityId.value, endCityId.value, 500)
  Object.assign(recSpots, d.data)
  showSpotModal.value = true
}
watch(showSpotModal, (v) => { if (v) openSpotModal() })

// ========== 自动定位（已改为 doLocate 函数，被空查询结果里的 "📍 自动定位" 选项触发） ==========

// ========== 地图（懒加载：规划后才初始化） ==========
const mapRef = ref(null)
const mapReady = ref(false)     // 🆕 地图是否已就绪
let AMap = null, map = null, polyline = null, highlightPoly = null, markers = [], stepMarkers = []
let stepSegments = []

onMounted(async () => {
  // 只加载城市/景点数据 — 地图 SDK 等到第一次要画路线时才加载
  const [c, s] = await Promise.all([apiCities(), apiSpots()])
  cities.value = c.data
  spots.value = s.data
  // 🆕 S6: 加载用户历史打分均值（用于优化反馈）
  loadUserMeans()
})
onUnmounted(() => { if (map) map.destroy() })

async function _ensureMap() {
  // 地图懒加载：第一次要画路线时才加载 AMap JS SDK + 创建地图实例
  if (map) return true
  try {
    AMap = await loadAMap()
    mapReady.value = true          // 触发 v-show 显示地图容器
    await nextTick()               // 等 DOM 更新
    map = createMap(mapRef.value)
    // Drawer 有动画 → 300ms 后 resize 确保地图正确铺满容器
    setTimeout(() => map?.resize(), 350)
    return true
  } catch (e) {
    console.warn('地图加载失败:', e)
    return false
  }
}

function clearMap() {
  for (const p of [polyline, highlightPoly]) if (p) { map.remove(p); }
  for (const m of [...markers, ...stepMarkers]) map.remove(m)
  polyline = highlightPoly = null; markers = []; stepMarkers = []; stepSegments = []
}

function buildStepSegments(planOpt) {
  const route = planOpt.route_coords || [], segs = []
  for (const s of planOpt.steps) {
    if (s.mode === '景点游览') {
      segs.push({ type: 'spot', coord: [s.from_lng, s.from_lat], label: s.from_name })
    } else {
      const a = [s.from_lng, s.from_lat], b = [s.to_lng, s.to_lat]
      let idxA = route.findIndex(c => Math.abs(c[0]-a[0])<0.002 && Math.abs(c[1]-a[1])<0.002)
      let idxB = route.findIndex(c => Math.abs(c[0]-b[0])<0.002 && Math.abs(c[1]-b[1])<0.002)
      if (idxA < 0) idxA = 0
      if (idxB < 0 || idxB < idxA) idxB = Math.min(idxA + 1, route.length - 1)
      segs.push({ type: 'transit', coords: route.slice(idxA, idxB + 1), startCoord: a, endCoord: b })
    }
  }
  return segs
}

async function drawRoute(planOpt) {
  if (!(await _ensureMap())) return
  clearMap()
  const coords = planOpt.route_coords || []
  if (coords.length < 2) return

  polyline = new AMap.Polyline({
    path: coords, strokeColor: '#cbd5e1', strokeWeight: 4, strokeOpacity: 0.4, lineJoin: 'round', showDir: true,
  })
  map.add(polyline)
  markers.push(new AMap.Marker({ position: coords[0], title: '出发', anchor: 'bottom-center' }))
  markers.push(new AMap.Marker({ position: coords[coords.length - 1], title: '到达', anchor: 'bottom-center' }))
  map.add(markers)
  stepSegments = buildStepSegments(planOpt)
  highlightStep(0)
  map.setFitView([polyline])
}

function highlightStep(idx) {
  if (!map || stepSegments.length === 0) return
  if (highlightPoly) { map.remove(highlightPoly); highlightPoly = null }
  for (const m of stepMarkers) map.remove(m); stepMarkers = []
  const seg = stepSegments[idx]
  if (!seg) return
  if (seg.type === 'transit') {
    highlightPoly = new AMap.Polyline({
      path: seg.coords, strokeColor: '#f43f5e', strokeWeight: 7, strokeOpacity: 0.95, lineJoin: 'round', showDir: true,
    })
    map.add(highlightPoly)
    stepMarkers.push(new AMap.Marker({ position: seg.startCoord, title: '起' }))
    stepMarkers.push(new AMap.Marker({ position: seg.endCoord, title: '终' }))
    map.add(stepMarkers)
    map.setFitView([highlightPoly])
  } else {
    const m = new AMap.Marker({ position: seg.coord, title: seg.label })
    map.add(m); stepMarkers.push(m)
    map.setZoomAndCenter(13, seg.coord)
  }
}

// ========== 规划 ==========
const plans = ref([])

const sortedPlans = computed(() => {
  const arr = [...plans.value]
  const w = { time_weight: 0.4, money_weight: 0.35, comfort_weight: 0.25 }
  const pref = [
    () => arr.sort((a, b) => a.total_time * w.time_weight + a.total_money * 0.5 * w.money_weight + a.total_discomfort * 10 * w.comfort_weight - (b.total_time * w.time_weight + b.total_money * 0.5 * w.money_weight + b.total_discomfort * 10 * w.comfort_weight)),
    () => arr.sort((a, b) => a.total_time - b.total_time),
    () => arr.sort((a, b) => a.total_money - b.total_money),
    () => arr.sort((a, b) => a.total_discomfort - b.total_discomfort),
  ][{ recommend: 0, fastest: 1, cheapest: 2, best: 3 }[sortTab.value]]
  pref()
  return arr
})

async function doPlan() {
  // 🆕 前置校验：必须有起点终点 + 经纬度（用户可能只输入文字未选下拉项）
  if (!startLat.value || !startLng.value || !endLat.value || !endLng.value) {
    ElMessage.warning('请先在搜索框选择有效的起点和终点（需从下拉选中带坐标的项）')
    return
  }
  if (!startName.value || !endName.value) {
    ElMessage.warning('请填写起点和终点名称')
    return
  }
  planning.value = true
  try {
    const d = await apiPlan({
      start_spot_id: startSpotId.value,
      end_spot_id: endSpotId.value,
      spot_ids: selectedSpotIds.value,
      start_lat: startLat.value, start_lng: startLng.value, start_name: startName.value,
      end_lat: endLat.value, end_lng: endLng.value, end_name: endName.value,
      transport_mode: transportMode.value,
    })
    if (d.ok) {
      plans.value = d.options
      ElMessage.success(`算法找到 ${d.count} 种方案 ✨`)
      // 只默认选中第一个卡片（高亮），不自动开 Drawer — 用户点"🗺️ 查看路线"才看地图
      if (plans.value.length) activeIdx.value = 0
      // 🆕 S5: 拉取出行提示（按起点+终点+景点名匹配）
      loadTravelTips()
    } else ElMessage.error(d.msg || '规划失败')
  } catch {} finally { planning.value = false }
}

const activeIdx = ref(-1)
const activePlan = computed(() => activeIdx.value >= 0 ? sortedPlans.value[activeIdx.value] : null)
const drawerVisible = ref(false)
const currentStepIdx = ref(0)
const userRating = ref(0)

// 🆕 当前步对象（含 amap_steps 逐步导航指令）
const currentStep = computed(() => activePlan.value?.steps?.[currentStepIdx.value] || null)

const currentStepPreview = computed(() => {
  const s = activePlan.value?.steps?.[currentStepIdx.value]
  if (!s) return '-'
  return `${s.mode} | ${s.from_name}→${s.to_name} | ${s.duration}min | ¥${s.cost}`
})

async function selectPlan(idx) {
  activeIdx.value = idx
  if (activePlan.value) {
    currentStepIdx.value = 0
    userRating.value = 0
    drawerVisible.value = true      // ① 先打开 Drawer，让 mapRef DOM 挂出来
    await nextTick()                // 等 drawer-map 渲染完毕
    drawRoute(activePlan.value)     // ② 再懒加载地图 + 画路线（里面 await _ensureMap）
  }
}

function nextStep() {
  if (!activePlan.value) return
  currentStepIdx.value = Math.min(currentStepIdx.value + 1, activePlan.value.steps.length - 1)
}
function prevStep() {
  if (!activePlan.value) return
  currentStepIdx.value = Math.max(0, currentStepIdx.value - 1)
}

// 🆕 返回修改：关 Drawer + 清方案 + 回到 Hero 输入态
function backToHero() {
  drawerVisible.value = false
  activeIdx.value = -1
  plans.value = []
  tipGroups.value = {}
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

// 🆕 S5: 拉取出行提示（起点+终点城市名匹配）
async function loadTravelTips() {
  const names = [startName.value, endName.value].filter(Boolean)
  if (!names.length) return
  try {
    const d = await apiTipMatch(names.join(','))
    if (d.ok) tipGroups.value = d.data.groups || {}
  } catch { /* 提示可选，失败不阻塞 */ }
}

function tipCatLabel(cat) {
  return { crowd: '👥 人潮', transit: '🚌 交通', tips: '💡 贴士', general: '📋 综合' }[cat] || cat
}

// 🆕 S6: 交通方式打分
const ratingScores = reactive({})   // { 驾车: 0, 公交: 1, ... }
const planModes = computed(() => {
  if (!activePlan.value?.steps) return []
  const modes = [...new Set(activePlan.value.steps.map(s => s.mode).filter(m => m && m !== '景点游览'))]
  // 初始化打分值
  for (const m of modes) {
    if (!(m in ratingScores)) ratingScores[m] = 0
  }
  return modes
})

async function submitModeRate(mode) {
  if (!activePlan.value?._plan_id) {
    ElMessage.warning('请先保存方案再打分')
    return
  }
  try {
    const d = await apiSubmitRate(activePlan.value._plan_id, mode, ratingScores[mode])
    if (d.ok) ElMessage.success(`已记录「${mode}」打分 ${ratingScores[mode]}，下次规划将参考`)
  } catch (e) {
    ElMessage.error('打分提交失败')
  }
}

// 🆕 S6: 加载用户历史均分（提示用）
const userMeans = ref({})
async function loadUserMeans() {
  if (!userStore.isLogin) return
  try {
    const d = await apiUserMeans()
    if (d.ok) userMeans.value = d.data || {}
  } catch {}
}

watch(currentStepIdx, (i) => { if (drawerVisible.value) highlightStep(i) })
watch(drawerVisible, (v) => { if (v) highlightStep(currentStepIdx.value) })

async function savePlan(opt) {
  if (!userStore.isLogin) { ElMessage.warning('请先登录'); return }
  try {
    const d = await apiSavePlan({
      start_city_id: startCityId.value, end_city_id: endCityId.value,
      spot_ids: selectedSpotIds.value,
      total_time: opt.total_time, total_money: opt.total_money,
      total_discomfort: opt.total_discomfort,
      route_detail: opt, steps: opt.steps,
      is_public: false,
    })
    opt._plan_id = d.plan_id
    ElMessage.success('💾 保存成功，可去个人中心查看')
  } catch {}
}

async function submitRating(rating) {
  if (!activePlan.value?._plan_id) { ElMessage.warning('请先保存后再评分'); return }
  await apiRatePlan(activePlan.value._plan_id, rating)
  ElMessage.success('⭐ 评分成功')
}

async function shareToPlaza() {
  if (!activePlan.value?._plan_id) { ElMessage.warning('请先保存后再分享'); return }
  const p = activePlan.value
  const title = prompt('给这条路线起个标题：',
    `${startName.value || '起点'} → ${endName.value || '终点'} 的旅行方案`)
  if (!title) return
  try {
    const d = await apiPlazaShare({
      plan_id: p._plan_id,
      title,
      description: `总耗时 ${formatTime(p.total_time)}，花费 ¥${p.total_money}`,
      origin_name: startName.value || '',
      dest_name: endName.value || '',
      route_data: {
        start_city_id: startCityId.value,
        end_city_id: endCityId.value,
        spot_ids: selectedSpotIds.value,
        total_time: p.total_time,
        total_money: p.total_money,
        total_discomfort: p.total_discomfort,
        steps: p.steps,
      },
    })
    if (d.ok) ElMessage.success('🌐 已分享到广场！')
  } catch (e) { ElMessage.error('分享失败') }
}

function formatTime(min) {
  const h = Math.floor(min / 60), m = min % 60
  return h ? `${h}h ${m}min` : `${m}min`
}
</script>

<style scoped>
.home { min-height: 100vh; background: #f4f6fb; }

/* ====== 顶栏 ====== */
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

/* ====== 主体布局 ====== */
/* 默认：一栏（左侧占满全屏） —— 没有规划结果时 */
.main {
  display: grid;
  grid-template-columns: 1fr;            /* 空态：一栏铺满 */
  min-height: calc(100vh - 53px);
  transition: grid-template-columns 0.3s ease;
}
/* 有规划结果：切成两栏，左 520px 右自适应 */
.main.has-results {
  grid-template-columns: 520px 1fr;
}
.left-panel {
  padding: 24px 32px;
  overflow-y: auto;
  max-height: calc(100vh - 53px);
  transition: all 0.3s ease;
}
/* 有结果时左侧缩小并加右边框 */
.main.has-results .left-panel {
  border-right: 1px solid #e5e7eb;
  padding: 20px;
}
.right-panel { position: relative; display: flex; flex-direction: column; overflow-y: auto; }

/* ====== Hero 搜索 ====== */
.hero {
  background: linear-gradient(135deg, #7c3aed 0%, #ec4899 100%);
  color: #fff; padding: 28px 32px; border-radius: 20px; margin-bottom: 24px;
  box-shadow: 0 8px 24px rgba(124,58,237,0.25);
}
/* 有规划结果时 Hero 缩小回到紧凑版 */
.main.has-results .hero { padding: 20px 24px; border-radius: 16px; margin-bottom: 20px; }
.hero-title { font-size: 26px; margin: 0 0 4px; }
.main.has-results .hero-title { font-size: 22px; }
.hero-sub { opacity: 0.9; font-size: 14px; margin: 0 0 20px; }
.main.has-results .hero-sub { font-size: 13px; margin-bottom: 18px; }
.search-row { display: grid; grid-template-columns: 1fr auto 1fr; gap: 10px; align-items: end; }
.search-label { font-size: 11px; opacity: 0.85; margin-bottom: 4px; }
.city-select :deep(.el-input__wrapper) { border-radius: 10px; }
.city-select :deep(.el-input) { width: 100%; }

/* === 🔍 搜索下拉样式（item 行，在 scoped 里因为在组件内） === */
.search-item-row {
  display: flex; flex-direction: column; padding: 8px 12px;
}
.search-item-row.row-poi { opacity: 0.85; }   /* 高德 POI 淡一点 */
.row-left { display: flex; align-items: center; gap: 8px; }
.row-icon { font-size: 14px; flex-shrink: 0; }
.search-item-label { font-size: 14px; color: #1f2937; font-weight: 500; }
.search-item-addr { font-size: 11px; color: #9ca3af; margin-top: 2px; }

.swap-btn {
  width: 36px; height: 40px; border-radius: 10px; background: rgba(255,255,255,0.2);
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; transition: all 0.3s;
}
.swap-btn:hover { transform: rotate(180deg); background: rgba(255,255,255,0.35); }
.opt-row {
  margin-top: 14px; display: flex; justify-content: space-between; align-items: center; gap: 8px;
}
.mode-group { display: inline-flex; flex-wrap: wrap; }
.ml-1 { margin-left: 6px; }
.plan-btn {
  width: 100%; margin-top: 14px; height: 44px; border: none; border-radius: 10px;
  background: #fff; color: #7c3aed; font-size: 15px; font-weight: 600; letter-spacing: 1px;
  cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 8px;
  transition: all 0.3s;
}
.plan-btn:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.2); }
.plan-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* ====== 景点推荐 ====== */
.rec-section { margin-top: 8px; }
.sec-head { margin-bottom: 12px; }
.sec-head h3 { margin: 0; font-size: 16px; }
.sec-sub { color: #9ca3af; font-size: 12px; }
.rec-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);  /* 🆕 固定 4 列 */
  gap: 16px;
}
/* 有规划结果时（左侧缩回 520px）限制为 2 列 */
.main.has-results .rec-grid { grid-template-columns: repeat(2, 1fr); }
.spot-card {
  background: #fff; border-radius: 14px; overflow: hidden; cursor: pointer;
  border: 2px solid transparent; transition: all 0.25s;
  box-shadow: 0 2px 10px rgba(0,0,0,0.06);
}
.spot-card:hover { transform: translateY(-4px); box-shadow: 0 10px 26px rgba(102,126,234,0.2); border-color: #667eea; }
.spot-card.selected { border-color: #7c3aed; }
.spot-img { position: relative; width: 100%; height: 160px; background: #eee; overflow: hidden; }  /* 🆕 放大 90→160 */
.spot-img img { width: 100%; height: 100%; object-fit: cover; transition: transform 0.3s; }
.spot-card:hover .spot-img img { transform: scale(1.08); }
.spot-overlay {
  position: absolute; bottom: 4px; left: 6px;
  background: rgba(0,0,0,0.5); color: #fff;
  font-size: 10px; padding: 2px 6px; border-radius: 4px;
}
.spot-quick-btn {
  position: absolute; top: 6px; right: 6px; width: 26px; height: 26px;
  border-radius: 50%; background: rgba(255,255,255,0.9); color: #7c3aed;
  display: flex; align-items: center; justify-content: center;
  font-size: 16px; font-weight: 700; cursor: pointer;
  box-shadow: 0 2px 6px rgba(0,0,0,0.15);
  transition: all 0.2s;
}
.spot-quick-btn:hover { background: #7c3aed; color: #fff; transform: scale(1.15); }
.spot-quick-btn.selected { background: #7c3aed; color: #fff; }
.spot-info { padding: 10px 12px; }
.spot-info h4 { margin: 0; font-size: 14px; }
.spot-info p { margin: 3px 0 0; font-size: 11px; color: #9ca3af; line-height: 1.4;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }

/* ====== 抽屉内地图 ====== */
.drawer-content { display: flex; flex-direction: column; gap: 14px; }
.drawer-map-wrap {
  position: relative;
  width: 100%;
  height: 280px;                 /* 抽屉里固定高度的大地图 */
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  background: #f3f4f6;
}
.drawer-map { width: 100%; height: 100%; }
.drawer-map-loading {
  position: absolute; inset: 0;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 8px; color: #6b7280; font-size: 13px;
}

/* ====== 规划结果 ====== */
.result-section {
  background: #fff; border-top: 1px solid #e5e7eb;
  max-height: 340px; overflow-y: auto; padding: 16px 20px;
}
.res-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.res-head h3 { margin: 0; font-size: 16px; }
.plan-scroll { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
.plan-card {
  background: #fafbfc; border: 1px solid #e5e7eb; border-radius: 10px;
  padding: 12px; cursor: pointer; transition: all 0.2s;
}
.plan-card:hover { border-color: #7c3aed; box-shadow: 0 4px 14px rgba(124,58,237,0.15); }
.plan-card.active { border-color: #7c3aed; background: #f3e8ff; }
.plan-head { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
.plan-title { font-weight: 600; font-size: 14px; color: #374151; }
.plan-tag { font-size: 11px; color: #f59e0b; }
.plan-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; margin-bottom: 10px; }
.stat { text-align: center; }
.stat .val { display: block; font-weight: 700; font-size: 15px; color: #7c3aed; }
.stat .val.dis { color: #f59e0b; }
.stat .lab { font-size: 10px; color: #9ca3af; }
.plan-actions { display: flex; gap: 6px; justify-content: flex-end; }

/* ====== 景点弹窗 ====== */
.no-rec { text-align: center; padding: 30px; color: #9ca3af; }
.no-rec p { margin: 10px 0 0; }
.spot-popup-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; max-height: 420px; overflow-y: auto; padding: 4px; }
.spot-popup-item {
  display: flex; gap: 10px; padding: 10px; border-radius: 10px; cursor: pointer;
  border: 1px solid #e5e7eb; transition: all 0.2s;
}
.spot-popup-item:hover { background: #f9fafb; border-color: #7c3aed; }
.spot-popup-item img { width: 70px; height: 54px; border-radius: 6px; object-fit: cover; flex-shrink: 0; }
.spi-info { flex: 1; min-width: 0; }
.spi-info h4 { margin: 0 0 4px; font-size: 13px; }
.spi-info p { margin: 0 0 4px; font-size: 11px; color: #9ca3af;
  display: -webkit-box; -webkit-line-clamp: 1; -webkit-box-orient: vertical; overflow: hidden; }
.spi-check { font-size: 13px; color: #7c3aed; font-weight: 600; align-self: center; }
.modal-footer { display: flex; justify-content: space-between; padding-top: 12px; border-top: 1px solid #f3f4f6; }

/* ====== 抽屉 ====== */
.plan-summary {
  background: linear-gradient(135deg, #f3e8ff, #fce7f3); padding: 14px; border-radius: 10px; margin-bottom: 12px;
}
.sum-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; font-size: 14px; }
.sum-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; text-align: center; }
.sum-stats strong { display: block; font-size: 16px; color: #7c3aed; }
.sum-stats span { font-size: 11px; color: #9ca3af; }

.current-step {
  padding: 10px 14px; background: #fff7ed; border-left: 3px solid #f97316;
  border-radius: 4px; font-size: 12px; margin-bottom: 10px;
}
.steps { padding: 8px 0; }
.drawer-actions {
  position: sticky; bottom: 0; background: #fff; padding: 12px;
  border-top: 1px solid #e5e7eb; margin-top: 16px;
}
.step-info { font-size: 12px; color: #9ca3af; margin-bottom: 8px; }
.step-btns { display: flex; gap: 6px; justify-content: flex-end; margin-bottom: 8px; }
.action-btns { display: flex; gap: 6px; justify-content: flex-end; }

/* ====== 景点详情弹窗 ====== */
.spot-detail :deep(.el-dialog__body) { padding: 0; }
.spot-detail { overflow: hidden; border-radius: 12px; }
.spot-detail .sd-img {
  position: relative; width: 100%; height: 240px; background: linear-gradient(135deg,#cbd5e1,#94a3b8);
  overflow: hidden;
}
.spot-detail .sd-img img { width: 100%; height: 100%; object-fit: cover; }
.spot-detail .sd-img-grad {
  position: absolute; inset: 0;
  background: linear-gradient(to top, rgba(0,0,0,0.7), rgba(0,0,0,0) 60%);
}
.spot-detail .sd-close {
  position: absolute; top: 12px; right: 12px;
  width: 32px; height: 32px; border-radius: 50%; border: none;
  background: rgba(0,0,0,0.4); color: #fff; font-size: 22px; line-height: 1;
  cursor: pointer; z-index: 10; transition: all 0.2s;
}
.spot-detail .sd-close:hover { background: rgba(0,0,0,0.7); transform: rotate(90deg); }
.spot-detail .sd-title {
  position: absolute; bottom: 40px; left: 20px; color: #fff;
  font-size: 26px; margin: 0; text-shadow: 0 2px 8px rgba(0,0,0,0.4);
}
.spot-detail .sd-meta {
  position: absolute; bottom: 14px; left: 20px; display: flex; gap: 10px; align-items: center;
  color: #fff; font-size: 12px;
}
.spot-detail .sd-coord { opacity: 0.85; }
.spot-detail .sd-body { padding: 20px; }
.spot-detail .sd-body h4 { margin: 0 0 10px; font-size: 15px; color: #374151; }
.spot-detail .sd-body p { margin: 0; color: #6b7280; line-height: 1.7; font-size: 14px; }
.spot-detail .sd-info-row { display: flex; gap: 12px; margin-top: 16px; }
.spot-detail .sd-info-cell {
  flex: 1; background: #f9fafb; border-radius: 10px; padding: 12px;
  display: flex; flex-direction: column; align-items: center;
}
.spot-detail .sd-info-val { font-size: 18px; font-weight: 700; color: #7c3aed; }
.spot-detail .sd-info-lab { font-size: 11px; color: #9ca3af; margin-top: 4px; }
.spot-detail .sd-actions {
  padding: 14px 20px; border-top: 1px solid #f3f4f6;
  display: flex; gap: 8px; justify-content: flex-end; flex-wrap: wrap;
}

/* === 🗺️ 高德逐步导航指令 === */
.amap-nav { margin-top: 8px; border-radius: 8px; }
.amap-nav :deep(.el-collapse-item__header) {
  background: linear-gradient(135deg, #10b98122, #3b82f622);
  font-weight: 600; font-size: 13px; border-radius: 8px !important;
}
.amap-nav :deep(.el-collapse-item__wrap) { background: #fafafa; }
.nav-title { display: flex; align-items: center; gap: 8px; }
.nav-instructions { max-height: 360px; overflow-y: auto; padding: 4px 0; }
.nav-row {
  display: grid; grid-template-columns: 28px 1fr auto;
  align-items: center; gap: 8px;
  padding: 8px 12px; margin: 2px 8px; border-radius: 6px;
  font-size: 13px; line-height: 1.5;
  transition: background 0.15s;
}
.nav-row:hover { background: #f0f9ff; }
.nav-num {
  width: 22px; height: 22px; border-radius: 50%;
  background: #3b82f6; color: #fff; font-size: 11px; font-weight: 600;
  display: flex; align-items: center; justify-content: center;
}
.nav-text { color: #1f2937; }
.nav-meta { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; font-size: 11px; color: #6b7280; }
.nav-road { color: #059669; }
.nav-dist { font-family: 'SF Mono', Menlo, monospace; font-weight: 500; color: #374151; }
.nav-dur { color: #9ca3af; }

/* === 🆕 首页景点分页 + 计数 === */
.sec-count { font-size: 13px; color: #9ca3af; font-weight: normal; margin-left: 6px; }
.rec-pager { display:flex; justify-content:center; padding: 14px 0 4px; border-top: 1px dashed #e5e7eb; margin-top: 6px; }

/* 🆕 S5: 出行提示卡 */
.tip-section { margin-top: 18px; padding-top: 14px; border-top: 2px dashed #e5e7eb; }
.tip-section h4 { margin: 0 0 10px; color: #1f2937; font-size: 15px; }

/* 🆕 估算方案时间轴（仿高德多模式样式） */
.est-timeline { margin: 12px 0; padding: 12px; background: #f9fafb; border-radius: 8px; border: 1px solid #e5e7eb; }
.est-banner { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.est-banner-text { font-size: 12px; color: #6b7280; }
.est-spine { position: relative; padding-left: 8px; }
.est-spine::before { content: ""; position: absolute; left: 16px; top: 18px; bottom: 18px; width: 2px; background: #3b82f6; }
.est-row { display: flex; align-items: flex-start; margin-bottom: 14px; position: relative; min-height: 32px; }
.est-row:last-child { margin-bottom: 0; }
.est-circle {
  width: 24px; height: 24px; border-radius: 50%; color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 600; flex-shrink: 0; z-index: 1; margin-right: 10px;
}
.est-origin { background: #10b981; }
.est-dest { background: #ef4444; }
.est-label { flex: 1; padding-top: 2px; }
.est-name { font-size: 14px; font-weight: 600; color: #1f2937; }
.est-coord { font-size: 11px; color: #9ca3af; font-family: 'SF Mono', Menlo, monospace; }
.est-transit {
  flex: 1; margin-left: 34px; padding: 8px 10px; background: #fff;
  border: 1px solid #d1d5db; border-radius: 6px;
}
.est-mode-pill {
  display: inline-block; padding: 2px 10px; border-radius: 12px;
  font-size: 12px; font-weight: 600; color: #fff; margin-bottom: 4px;
}
.mode-飞机 { background: #3b82f6; }
.mode-高铁 { background: #1e40af; }
.mode-大巴 { background: #0ea5e9; }
.mode-打车 { background: #f59e0b; color: #fff; }
.est-transit-info { font-size: 13px; color: #1f2937; display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.est-time { font-weight: 600; }
.est-money { color: #059669; font-weight: 600; }
.est-dist, .est-transfer { color: #6b7280; font-size: 12px; }
.est-note { font-size: 11px; color: #9ca3af; margin-top: 4px; }
.tip-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
.tip-city-block { display: flex; flex-direction: column; gap: 8px; }
.tip-city-head { font-size: 13px; color: #409EFF; font-weight: 600; padding-left: 4px; border-left: 3px solid #409EFF; }
.tip-card {
  background: #fff; border: 1px solid #e5e7eb; border-radius: 8px;
  padding: 10px 12px; box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
.tip-cat { font-size: 11px; color: #6b7280; margin-bottom: 4px; }
.tip-title { font-size: 13px; font-weight: 600; color: #1f2937; margin-bottom: 4px; }
.tip-content { font-size: 12px; color: #4b5563; line-height: 1.5; }
.tip-card.cat-crowd { border-left: 3px solid #f59e0b; }
.tip-card.cat-transit { border-left: 3px solid #3b82f6; }
.tip-card.cat-tips { border-left: 3px solid #10b981; }
.tip-card.cat-general { border-left: 3px solid #8b5cf6; }

/* 🆕 S6: 打分卡 */
.rate-section {
  margin: 14px 0; padding: 12px; background: #f0f9ff;
  border: 1px solid #d0e8fc; border-radius: 8px;
}
.rate-head { display: flex; justify-content: space-between; align-items: center; font-weight: 600; font-size: 14px; }
.rate-hint { font-size: 11px; color: #6b7280; margin: 4px 0 8px; }
.rate-row { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.rate-mode { width: 60px; font-size: 13px; color: #374151; }

/* === 🔍 搜索下拉面板（独立全局 style，因为 el-autocomplete 面板 teleport 到 body） === */
</style>

<style>
/* 下拉面板整体 */
.el-autocomplete-suggestion.search-dropdown,
.el-autocomplete-suggestion {
  border-radius: 12px !important;
  box-shadow: 0 8px 28px rgba(0,0,0,0.12) !important;
  border: 1px solid #f1f5f9 !important;
  padding: 4px 0 !important;
  overflow: hidden;
  font-family: -apple-system, 'Segoe UI', Roboto, 'PingFang SC', 'Microsoft YaHei', sans-serif;
}
.el-autocomplete-suggestion .el-autocomplete-suggestion__wrap {
  max-height: 360px !important;
}
.el-autocomplete-suggestion li {
  padding: 0 !important;
  line-height: normal !important;
}
.el-autocomplete-suggestion li:hover {
  background: #f5f3ff !important;
}
.el-autocomplete-suggestion .el-icon.is-loading {
  margin: 14px auto;
}

/* 分组 header */
.dropdown-section {
  padding: 10px 14px 4px !important;
  font-size: 11px; font-weight: 600; color: #9ca3af !important;
  letter-spacing: 0.5px; text-transform: uppercase;
  background: #fafafa; border-bottom: 1px solid #f3f4f6;
  margin-top: 8px;
  cursor: default;
  pointer-events: none;
}

/* 高亮 mark */
.search-item-label mark {
  background: linear-gradient(120deg, #fde68a 0%, #fcd34d 100%);
  color: #78350f; padding: 0 3px; border-radius: 3px; font-weight: 700;
}
</style>
