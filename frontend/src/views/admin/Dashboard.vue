<template>
  <div class="page">
    <h3>📊 数据可视化仪表盘</h3>
    <p class="desc">NSGA-II 算法运行监控 · 帕累托前沿 · 超体积收敛 · 规划统计</p>

    <!-- 总览统计卡 -->
    <div class="stat-row">
      <el-card class="stat-card" shadow="hover">
        <div class="stat-item">
          <span class="stat-icon">👥</span>
          <div class="stat-info">
            <span class="stat-num">{{ overview.users ?? '-' }}</span>
            <span class="stat-label">用户总数</span>
          </div>
        </div>
      </el-card>
      <el-card class="stat-card" shadow="hover">
        <div class="stat-item">
          <span class="stat-icon">🗺️</span>
          <div class="stat-info">
            <span class="stat-num">{{ overview.plans ?? '-' }}</span>
            <span class="stat-label">规划数</span>
          </div>
        </div>
      </el-card>
      <el-card class="stat-card" shadow="hover">
        <div class="stat-item">
          <span class="stat-icon">🎯</span>
          <div class="stat-info">
            <span class="stat-num">{{ overview.solutions ?? '-' }}</span>
            <span class="stat-label">帕累托解</span>
          </div>
        </div>
      </el-card>
      <el-card class="stat-card" shadow="hover">
        <div class="stat-item">
          <span class="stat-icon">📈</span>
          <div class="stat-info">
            <span class="stat-num">{{ overview.iteration_logs ?? '-' }}</span>
            <span class="stat-label">迭代日志</span>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 算法统计行 -->
    <div class="stat-row">
      <el-card class="stat-card" shadow="hover">
        <div class="stat-item">
          <span class="stat-icon small">⚖️</span>
          <div class="stat-info">
            <span class="stat-num small">{{ algStats.hv?.mean ?? '-' }}</span>
            <span class="stat-label">平均 HV</span>
          </div>
        </div>
      </el-card>
      <el-card class="stat-card" shadow="hover">
        <div class="stat-item">
          <span class="stat-icon small">🔝</span>
          <div class="stat-info">
            <span class="stat-num small">{{ algStats.hv?.max ?? '-' }}</span>
            <span class="stat-label">最大 HV</span>
          </div>
        </div>
      </el-card>
      <el-card class="stat-card" shadow="hover">
        <div class="stat-item">
          <span class="stat-icon small">📊</span>
          <div class="stat-info">
            <span class="stat-num small">{{ algStats.avg_pareto_per_plan ?? '-' }}</span>
            <span class="stat-label">每规划平均解数</span>
          </div>
        </div>
      </el-card>
      <el-card class="stat-card" shadow="hover">
        <div class="stat-item">
          <span class="stat-icon small">⏱️</span>
          <div class="stat-info">
            <span class="stat-num small">{{ algStats.solutions?.mean_elapsed ?? '-' }}s</span>
            <span class="stat-label">NSGA-II 平均耗时</span>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 规划选择 -->
    <el-card class="block-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span>🔬 NSGA-II 运行详情</span>
          <el-select
            v-model="selectedPlanId"
            placeholder="选择规划查看算法运行详情"
            filterable
            style="width: 360px"
            @change="loadPlanDetails"
          >
            <el-option
              v-for="p in recentPlans"
              :key="p.id"
              :label="`#${p.id} ${p.username || ''} · ${p.solution_count}解/${p.iteration_log_count}代 · HV${p.last_hv ?? '-'}`"
              :value="p.id"
            />
          </el-select>
        </div>
      </template>

      <div v-if="!selectedPlanId" class="empty-tip">
        👆 请在上方选择一个规划，查看该规划的 HV 收敛曲线和帕累托散点
      </div>

      <div v-else class="chart-grid">
        <!-- HV 收敛曲线 -->
        <div class="chart-box">
          <div class="chart-title">📈 超体积 HV 收敛曲线</div>
          <div ref="hvChartRef" class="chart-canvas"></div>
        </div>

        <!-- 帕累托散点 -->
        <div class="chart-box">
          <div class="chart-title">🎯 帕累托前沿散点（费用 vs 时间，颜色=不适感）</div>
          <div ref="paretoChartRef" class="chart-canvas"></div>
        </div>

        <!-- 帕累托解数曲线 -->
        <div class="chart-box">
          <div class="chart-title">🧮 帕累托解数随代数变化</div>
          <div ref="paretoCountChartRef" class="chart-canvas"></div>
        </div>

        <!-- 最优目标值曲线 -->
        <div class="chart-box">
          <div class="chart-title">⏱️ 当代最优时间/费用</div>
          <div ref="bestObjChartRef" class="chart-canvas"></div>
        </div>
      </div>
    </el-card>

    <!-- 最近规划表 -->
    <el-card class="block-card" shadow="never">
      <template #header><span>🗂️ 最近规划（含 NSGA-II 运行指标）</span></template>
      <el-table :data="recentPlans" size="small" stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="username" label="用户" width="120" />
        <el-table-column label="耗时/费用" width="160">
          <template #default="{ row }">
            <span>{{ row.total_time }}分 / ¥{{ row.total_money }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="solution_count" label="方案数" width="90" />
        <el-table-column prop="iteration_log_count" label="迭代代数" width="100" />
        <el-table-column label="最新 HV" width="120">
          <template #default="{ row }">
            <span :class="{ 'hv-good': row.last_hv }">{{ row.last_hv ?? '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="公开" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_public ? 'success' : 'info'" size="small">
              {{ row.is_public ? '公开' : '私有' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import {
  getDashboardOverview, getHvConvergence, getParetoScatter,
  getRecentPlans, getAlgStats,
} from '@/api/admin'

const overview = ref({})
const algStats = ref({})
const recentPlans = ref([])
const selectedPlanId = ref(null)

const hvChartRef = ref(null)
const paretoChartRef = ref(null)
const paretoCountChartRef = ref(null)
const bestObjChartRef = ref(null)
let hvChart, paretoChart, paretoCountChart, bestObjChart

async function loadOverview() {
  try {
    const d = await getDashboardOverview()
    if (d.ok) overview.value = d.data
  } catch { ElMessage.error('加载总览失败') }
}

async function loadAlgStats() {
  try {
    const d = await getAlgStats()
    if (d.ok) algStats.value = d.data
  } catch { ElMessage.error('加载算法统计失败') }
}

async function loadRecentPlans() {
  try {
    const d = await getRecentPlans(20)
    if (d.ok) recentPlans.value = d.data
  } catch { ElMessage.error('加载最近规划失败') }
}

async function loadPlanDetails(pid) {
  if (!pid) return
  await nextTick()
  await Promise.all([loadHvChart(pid), loadParetoChart(pid)])
}

async function loadHvChart(pid) {
  try {
    const d = await getHvConvergence(pid)
    if (!d.ok) return
    const s = d.data.series
    if (!s.length) { ElMessage.warning('该规划无迭代日志'); return }

    if (!hvChart) hvChart = echarts.init(hvChartRef.value)
    hvChart.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: 60, right: 50, top: 30, bottom: 40 },
      xAxis: { name: '代数', type: 'category', data: s.map(x => x.gen) },
      yAxis: [
        { name: 'HV', type: 'value' },
        { name: '解数', type: 'value', position: 'right' },
      ],
      series: [
        { name: 'HV', type: 'line', smooth: true, data: s.map(x => x.hv), itemStyle: { color: '#409EFF' }, areaStyle: { opacity: 0.15 } },
        { name: '帕累托解数', type: 'line', yAxisIndex: 1, data: s.map(x => x.pareto_count), itemStyle: { color: '#67C23A' } },
      ],
    })

    // 帕累托解数小图
    if (!paretoCountChart) paretoCountChart = echarts.init(paretoCountChartRef.value)
    paretoCountChart.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: 50, right: 20, top: 20, bottom: 30 },
      xAxis: { name: '代数', type: 'category', data: s.map(x => x.gen) },
      yAxis: { name: '解数', type: 'value' },
      series: [{ type: 'bar', data: s.map(x => x.pareto_count), itemStyle: { color: '#67C23A' } }],
    })

    // 最优目标小图
    if (!bestObjChart) bestObjChart = echarts.init(bestObjChartRef.value)
    bestObjChart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['最短时间', '最低费用'], top: 0 },
      grid: { left: 60, right: 60, top: 30, bottom: 30 },
      xAxis: { name: '代数', type: 'category', data: s.map(x => x.gen) },
      yAxis: [
        { name: '时间(分)', type: 'value' },
        { name: '费用(元)', type: 'value', position: 'right' },
      ],
      series: [
        { name: '最短时间', type: 'line', smooth: true, data: s.map(x => x.best_time), itemStyle: { color: '#E6A23C' } },
        { name: '最低费用', type: 'line', yAxisIndex: 1, smooth: true, data: s.map(x => x.best_cost), itemStyle: { color: '#F56C6C' } },
      ],
    })
  } catch (e) { ElMessage.error('HV 收敛曲线加载失败') }
}

async function loadParetoChart(pid) {
  try {
    const d = await getParetoScatter(pid)
    if (!d.ok) return
    const pts = d.data
    if (!pts.length) { ElMessage.warning('该规划无帕累托解'); return }

    if (!paretoChart) paretoChart = echarts.init(paretoChartRef.value)
    paretoChart.setOption({
      tooltip: {
        trigger: 'item',
        formatter: p => `时间: ${p.value[0]}分<br/>费用: ¥${p.value[1]}<br/>不适感: ${p.value[2]}<br/>标签: ${p.data.label || '-'}`
      },
      grid: { left: 60, right: 30, top: 30, bottom: 50 },
      xAxis: { name: '时间(分)', type: 'value' },
      yAxis: { name: '费用(元)', type: 'value' },
      visualMap: {
        min: Math.min(...pts.map(p => p.experience)),
        max: Math.max(...pts.map(p => p.experience)),
        dimension: 2,
        inRange: { color: ['#67C23A', '#E6A23C', '#F56C6C'] },
        text: ['不适感低', '不适感高'],
        right: 0, top: 'middle',
      },
      series: [{
        type: 'scatter',
        data: pts.map(p => ({
          value: [p.time, p.cost, p.experience],
          label: p.label,
        })),
        symbolSize: 14,
      }],
    })
  } catch { ElMessage.error('帕累托散点加载失败') }
}

function handleResize() {
  hvChart?.resize(); paretoChart?.resize()
  paretoCountChart?.resize(); bestObjChart?.resize()
}

onMounted(async () => {
  await Promise.all([loadOverview(), loadAlgStats(), loadRecentPlans()])
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  hvChart?.dispose(); paretoChart?.dispose()
  paretoCountChart?.dispose(); bestObjChart?.dispose()
})
</script>

<style scoped>
.page { padding: 16px; background: #f5f7fa; min-height: calc(100vh - 120px); }
.page h3 { margin: 0 0 4px; color: #1f2937; font-size: 18px; }
.desc { color: #6b7280; font-size: 13px; margin: 0 0 16px; }

.stat-row {
  display: grid; grid-template-columns: repeat(4, 1fr);
  gap: 16px; margin-bottom: 16px;
}
.stat-card :deep(.el-card__body) { padding: 18px; }
.stat-item { display: flex; align-items: center; gap: 14px; }
.stat-icon {
  font-size: 30px; width: 52px; height: 52px;
  display: flex; align-items: center; justify-content: center;
  background: #ecf5ff; border-radius: 10px; flex-shrink: 0;
}
.stat-icon.small { font-size: 24px; width: 46px; height: 46px; }
.stat-info { display: flex; flex-direction: column; }
.stat-num { font-size: 24px; font-weight: 700; color: #409EFF; line-height: 1.2; }
.stat-num.small { font-size: 20px; }
.stat-label { font-size: 12px; color: #909399; margin-top: 2px; }

.block-card { margin-bottom: 16px; }
.card-header {
  display: flex; justify-content: space-between;
  align-items: center; font-weight: 600;
}
.empty-tip {
  padding: 40px; text-align: center; color: #909399; font-size: 14px;
}

.chart-grid {
  display: grid; grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.chart-box {
  background: #fafbfc; border: 1px solid #ebeef5;
  border-radius: 8px; padding: 12px;
}
.chart-title {
  font-size: 13px; color: #606266; margin-bottom: 8px; font-weight: 600;
}
.chart-canvas { width: 100%; height: 280px; }

.hv-good { color: #67C23A; font-weight: 600; }
</style>
