<template>
  <div class="page">
    <h3>💰 成本矩阵</h3>
    <p class="desc">维护城市间交通费用、时间成本等矩阵数据</p>

    <div class="toolbar">
      <el-select
        v-model="fromFilter"
        placeholder="出发城市"
        clearable
        style="width: 160px"
        @change="loadMatrix"
      >
        <el-option v-for="c in cityOptions" :key="'f' + c.id" :label="c.name" :value="c.id" />
      </el-select>
      <el-select
        v-model="toFilter"
        placeholder="目的城市"
        clearable
        style="width: 160px"
        @change="loadMatrix"
      >
        <el-option v-for="c in cityOptions" :key="'t' + c.id" :label="c.name" :value="c.id" />
      </el-select>
      <el-button type="primary" @click="loadMatrix()">🔍 筛选</el-button>

      <!-- 📊 覆盖率徽章 -->
      <el-tag v-if="coverageStats" :type="coverageStats.coverage_pct >= 95 ? 'success' : coverageStats.coverage_pct >= 70 ? 'warning' : 'danger'" effect="dark" style="margin-left: 8px">
        📊 覆盖率 {{ coverageStats.covered_edges }}/{{ coverageStats.total_possible_edges }} = {{ coverageStats.coverage_pct }}%
      </el-tag>

      <div style="flex: 1" />
      <!-- 🔧 一键补全 -->
      <el-button
        type="warning"
        :loading="fillingAmap"
        @click="handleFillFromAmap"
        :disabled="coverageStats?.coverage_pct >= 99.9"
      >
        🔧 一键补全缺失边（高德驾车）
      </el-button>
      <el-button type="success" @click="openDialog(null)">➕ 新增条目</el-button>
    </div>

    <el-table :data="matrix" border stripe style="width: 100%" max-height="calc(100vh - 200px)">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="出发 → 目的" min-width="200">
        <template #default="{ row }">
          <span class="route-label">
            {{ cityName(row.from_city_id) }}
            <span class="arrow"> → </span>
            {{ cityName(row.to_city_id) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="mode" label="方式" width="100" />
      <el-table-column label="时间(分钟)" width="110">
        <template #default="{ row }">{{ row.time_cost ?? '-' }}</template>
      </el-table-column>
      <el-table-column label="金钱(元)" width="100">
        <template #default="{ row }">¥{{ row.money_cost ?? '-' }}</template>
      </el-table-column>
      <el-table-column label="换乘次数" width="100">
        <template #default="{ row }">{{ row.transfer_times ?? '-' }}</template>
      </el-table-column>
      <el-table-column label="不适感" width="90">
        <template #default="{ row }">{{ row.discomfort != null ? Number(row.discomfort).toFixed(1) : '-' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" link @click="openDialog(row)">编辑</el-button>
          <el-popconfirm title="确认删除该成本条目？此操作不可恢复" @confirm="handleDelete(row)">
            <template #reference>
              <el-button type="danger" size="small" link>删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="dialogVisible"
      :title="editing ? '编辑成本条目' : '新增成本条目'"
      width="500px"
      destroy-on-close
    >
      <el-form :model="form" label-width="100px" style="padding-right: 20px">
        <el-form-item label="出发城市">
          <el-select v-model="form.from_city_id" placeholder="选择出发城市" style="width: 100%">
            <el-option v-for="c in cityOptions" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="目的城市">
          <el-select v-model="form.to_city_id" placeholder="选择目的城市" style="width: 100%">
            <el-option v-for="c in cityOptions" :key="'t' + c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="交通方式">
          <el-input v-model="form.mode" placeholder="例如：高铁 / 汽车 / 步行" />
        </el-form-item>
        <el-form-item label="时间(分钟)">
          <el-input-number v-model="form.time_cost" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="金钱(元)">
          <el-input-number v-model="form.money_cost" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="换乘次数">
          <el-input-number v-model="form.transfer_times" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="不适感">
          <el-input-number v-model="form.discomfort" :min="0" :max="10" :precision="1" :step="0.5" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getCostMatrix, createCostEntry, updateCostEntry, deleteCostEntry, getCitiesAdmin, fillCostFromAmap } from '@/api/admin'

const fromFilter = ref(null)
const toFilter = ref(null)
const matrix = ref([])
const cityOptions = ref([])
const dialogVisible = ref(false)
const editing = ref(null)
const coverageStats = ref(null)   // 📊 覆盖率统计
const fillingAmap = ref(false)   // 🔧 补全中 loading

const form = reactive({
  from_city_id: null, to_city_id: null, mode: '',
  time_cost: 60, money_cost: 10.0, transfer_times: 0, discomfort: 1.0,
})

function cityName(id) {
  const c = cityOptions.value.find(x => x.id === id)
  return c?.name || (`#${id}`)
}

async function loadCities() {
  try {
    const data = await getCitiesAdmin()
    const payload = data.data || data
    cityOptions.value = payload.items || payload.list || payload.cities || (Array.isArray(payload) ? payload : [])
  } catch { /* ignore */ }
}

async function loadMatrix() {
  try {
    const params = {}
    if (fromFilter.value) params.from_city_id = fromFilter.value
    if (toFilter.value) params.to_city_id = toFilter.value
    const data = await getCostMatrix(params)
    // data = { ok, stats, data: [...] }
    // 原始响应体里 stats 在顶层，data 字段是表格行
    coverageStats.value = data.stats || null
    const rows = data.data
    matrix.value = Array.isArray(rows) ? rows : []
  } catch (e) {
    console.error(e)
  }
}

// 🔧 一键补全缺失边
async function handleFillFromAmap() {
  try {
    await ElMessageBox.confirm(
      '将调用高德驾车 API 填充所有缺失的城市对成本矩阵。\n\n' +
      '预计填补约 300+ 条缺失边，耗时约 1-2 分钟。\n' +
      '高德每日免费额度 5000 次，本次约消耗 300 次。\n\n' +
      '⚠️ 建议先备份数据库。确认开始？',
      '一键补全 CostMatrix',
      { confirmButtonText: '开始补全', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }

  fillingAmap.value = true
  try {
    ElMessage.info('🔧 正在调用高德驾车 API 补全，请稍候...')
    const d = await fillCostFromAmap({ mode: '综合' })
    const s = d.stats || {}
    ElMessage.success(
      `✅ 补全完成！\n` +
      `成功 ${s.filled_forward} 条 | 失败 ${s.failed} 条\n` +
      `耗时 ${s.elapsed_sec}s | 当前覆盖率 ${s.mode_coverage_pct}%`
    )
    await loadMatrix()   // 刷新表格和覆盖率徽章
  } catch (e) {
    console.error(e)
    ElMessage.error('补全失败：' + (e?.message || '未知错误'))
  } finally {
    fillingAmap.value = false
  }
}

function openDialog(row) {
  editing.value = row
  if (row) {
    Object.assign(form, {
      from_city_id: row.from_city_id,
      to_city_id: row.to_city_id,
      mode: row.mode || '',
      time_cost: row.time_cost ?? 60,
      money_cost: row.money_cost ?? 10,
      transfer_times: row.transfer_times ?? 0,
      discomfort: row.discomfort ?? 1.0,
    })
  } else {
    Object.assign(form, {
      from_city_id: null, to_city_id: null, mode: '',
      time_cost: 60, money_cost: 10.0, transfer_times: 0, discomfort: 1.0,
    })
  }
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!form.from_city_id || !form.to_city_id) { ElMessage.warning('请选择出发和目的城市'); return }
  if (!form.mode) { ElMessage.warning('请输入交通方式'); return }
  if (form.from_city_id === form.to_city_id) { ElMessage.warning('出发和目的城市不能相同'); return }
  try {
    if (editing.value) {
      await updateCostEntry(editing.value.id, { ...form })
      ElMessage.success('更新成功')
    } else {
      await createCostEntry({ ...form })
      ElMessage.success('新增成功')
    }
    dialogVisible.value = false
    loadMatrix()
  } catch (e) {
    console.error(e)
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确认删除 ${cityName(row.from_city_id)} → ${cityName(row.to_city_id)} (${row.mode}) 这条成本数据？`,
      '删除确认',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' }
    )
    await deleteCostEntry(row.id)
    ElMessage.success('删除成功')
    loadMatrix()
  } catch (e) {
    if (e !== 'cancel') console.error(e)
  }
}

onMounted(async () => {
  await loadCities()
  loadMatrix()
})
</script>

<style scoped>
.page {
  padding: 16px;
  background: #f5f7fa;
  min-height: calc(100vh - 120px);
}
.page h3 { margin: 0 0 4px; color: #1f2937; font-size: 18px; }
.desc { color: #6b7280; font-size: 13px; margin: 0 0 12px; }
.toolbar {
  display: flex; gap: 10px; align-items: center; margin-bottom: 12px;
  background: #fff; padding: 12px; border-radius: 6px; border: 1px solid #ebeef5;
}
.route-label { font-weight: 600; color: #303133; }
.route-label .arrow { color: #909399; margin: 0 6px; }
</style>
