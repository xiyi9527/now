<template>
  <div class="page">
    <h3>🏞️ 景点管理</h3>
    <p class="desc">维护景点库，关联所属城市、坐标、建议游览时长</p>

    <div class="toolbar">
      <el-input
        v-model="search"
        placeholder="搜索景点名称..."
        clearable
        style="width: 220px"
        @clear="loadSpots()"
        @keyup.enter="loadSpots()"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <el-select
        v-model="cityFilter"
        placeholder="全部城市"
        clearable
        style="width: 180px"
        @change="loadSpots"
      >
        <el-option
          v-for="c in cityOptions"
          :key="c.id"
          :label="c.name"
          :value="c.id"
        />
      </el-select>
      <el-button type="primary" @click="loadSpots()">🔍 搜索</el-button>
      <div style="flex: 1" />
      <el-button type="success" @click="openDialog(null)">➕ 新增景点</el-button>
    </div>

    <el-table :data="spots" border stripe style="width: 100%" max-height="calc(100vh - 200px)">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="name" label="景点名称" min-width="160" />
      <el-table-column label="所属城市" width="140">
        <template #default="{ row }">
          {{ row.city_name || cityName(row.city_id) }}
        </template>
      </el-table-column>
      <el-table-column label="简介" min-width="220">
        <template #default="{ row }">
          <div class="desc-text">{{ row.description || '—' }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="lat" label="纬度" width="100" />
      <el-table-column prop="lng" label="经度" width="100" />
      <el-table-column label="浏览时长(min)" width="130">
        <template #default="{ row }">
          {{ row.cost_time_extra ?? '-' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" link @click="openDialog(row)">编辑</el-button>
          <el-popconfirm title="确认删除该景点？此操作不可恢复" @confirm="handleDelete(row)">
            <template #reference>
              <el-button type="danger" size="small" link>删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="dialogVisible"
      :title="editing ? '编辑景点' : '新增景点'"
      width="560px"
      destroy-on-close
    >
      <el-form :model="form" label-width="100px" style="padding-right: 20px">
        <el-form-item label="景点名称">
          <el-input v-model="form.name" placeholder="请输入景点名称" />
        </el-form-item>
        <el-form-item label="所属城市">
          <el-select v-model="form.city_id" placeholder="请选择城市" style="width: 100%">
            <el-option v-for="c in cityOptions" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="简介">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="景点描述..." />
        </el-form-item>
        <el-form-item label="图片 URL">
          <el-input v-model="form.img_url" placeholder="https://..." />
        </el-form-item>
        <el-form-item label="纬度 lat">
          <el-input-number v-model="form.lat" :precision="6" :step="0.01" style="width: 100%" />
        </el-form-item>
        <el-form-item label="经度 lng">
          <el-input-number v-model="form.lng" :precision="6" :step="0.01" style="width: 100%" />
        </el-form-item>
        <el-form-item label="浏览时长">
          <el-input-number v-model="form.cost_time_extra" :min="0" :step="10" style="width: 100%" />
          <div class="hint">分钟</div>
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
import { getSpotsAdmin, createSpot, updateSpot, deleteSpot, getCitiesAdmin } from '@/api/admin'

const search = ref('')
const cityFilter = ref(null)
const spots = ref([])
const cityOptions = ref([])
const dialogVisible = ref(false)
const editing = ref(null)

const form = reactive({
  name: '', city_id: null, description: '', img_url: '',
  lat: 30.0, lng: 120.0, cost_time_extra: 60,
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

async function loadSpots() {
  try {
    const params = {}
    if (search.value) params.keyword = search.value
    if (cityFilter.value) params.city_id = cityFilter.value
    const data = await getSpotsAdmin(params)
    const payload = data.data || data
    spots.value = payload.items || payload.list || payload.spots || (Array.isArray(payload) ? payload : [])
  } catch (e) {
    console.error(e)
  }
}

function openDialog(row) {
  editing.value = row
  if (row) {
    Object.assign(form, {
      name: row.name || '',
      city_id: row.city_id,
      description: row.description || '',
      img_url: row.img_url || '',
      lat: Number(row.lat) || 30.0,
      lng: Number(row.lng) || 120.0,
      cost_time_extra: row.cost_time_extra ?? 60,
    })
  } else {
    Object.assign(form, {
      name: '', city_id: null, description: '', img_url: '',
      lat: 30.0, lng: 120.0, cost_time_extra: 60,
    })
  }
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!form.name) { ElMessage.warning('请输入景点名称'); return }
  if (!form.city_id) { ElMessage.warning('请选择所属城市'); return }
  try {
    if (editing.value) {
      await updateSpot(editing.value.id, { ...form })
      ElMessage.success('更新成功')
    } else {
      await createSpot({ ...form })
      ElMessage.success('新增成功')
    }
    dialogVisible.value = false
    loadSpots()
  } catch (e) {
    console.error(e)
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确认删除景点 "${row.name}"？此操作不可恢复`,
      '删除确认',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' }
    )
    await deleteSpot(row.id)
    ElMessage.success('删除成功')
    loadSpots()
  } catch (e) {
    if (e !== 'cancel') console.error(e)
  }
}

onMounted(async () => {
  await loadCities()
  loadSpots()
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
.desc-text {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-size: 13px;
  color: #606266;
  line-height: 1.5;
}
.hint { font-size: 12px; color: #909399; margin-top: 4px; }
</style>
