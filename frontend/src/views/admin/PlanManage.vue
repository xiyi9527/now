<template>
  <div class="page">
    <h3>🗺️ 规划记录</h3>
    <p class="desc">查看所有用户的规划历史，支持删除不当内容</p>

    <div class="toolbar">
      <div style="flex: 1" />
      <el-button type="primary" @click="loadPlans()">🔄 刷新</el-button>
    </div>

    <el-table :data="plans" border stripe style="width: 100%" max-height="calc(100vh - 200px)">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="用户" width="140">
        <template #default="{ row }">
          {{ row.username || row.user?.username || `#${row.user_id || row.user?.id || '-'}` }}
        </template>
      </el-table-column>
      <el-table-column label="起点 → 终点" min-width="200">
        <template #default="{ row }">
          <span class="route-label">
            {{ row.start_city_name || cityName(row.start_city_id) }}
            <span class="arrow"> → </span>
            {{ row.end_city_name || cityName(row.end_city_id) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="时间(min)" width="110">
        <template #default="{ row }">{{ row.total_time ?? '-' }}</template>
      </el-table-column>
      <el-table-column label="花费(元)" width="110">
        <template #default="{ row }">¥{{ row.total_money ?? '-' }}</template>
      </el-table-column>
      <el-table-column label="不适感" width="90">
        <template #default="{ row }">{{ row.total_discomfort != null ? Number(row.total_discomfort).toFixed(1) : '-' }}</template>
      </el-table-column>
      <el-table-column label="公开" width="90">
        <template #default="{ row }">
          <el-tag v-if="row.is_public" type="success" size="small">公开</el-tag>
          <span v-else style="color: #c0c4cc; font-size: 12px">私有</span>
        </template>
      </el-table-column>
      <el-table-column label="评分" width="80">
        <template #default="{ row }">
          <el-rate v-if="row.rating" :model-value="row.rating" disabled size="small" />
          <span v-else style="color: #c0c4cc; font-size: 12px">—</span>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="170" />
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-popconfirm title="确认删除该规划？此操作不可恢复" @confirm="handleDelete(row)">
            <template #reference>
              <el-button type="danger" size="small" link>删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getPlansAdmin, deletePlan, getCitiesAdmin } from '@/api/admin'

const plans = ref([])
const cityOptions = ref([])

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

async function loadPlans() {
  try {
    const data = await getPlansAdmin()
    const payload = data.data || data
    plans.value = payload.items || payload.list || payload.plans || (Array.isArray(payload) ? payload : [])
  } catch (e) {
    console.error(e)
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确认删除规划 #${row.id}？此操作不可恢复`,
      '删除确认',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' }
    )
    await deletePlan(row.id)
    ElMessage.success('删除成功')
    loadPlans()
  } catch (e) {
    if (e !== 'cancel') console.error(e)
  }
}

onMounted(async () => {
  await loadCities()
  loadPlans()
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
