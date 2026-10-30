<template>
  <div class="page">
    <h3>🏙️ 城市管理</h3>
    <p class="desc">维护城市基础数据，新增、编辑、删除城市信息</p>

    <div class="toolbar">
      <el-input
        v-model="search"
        placeholder="搜索城市名称..."
        clearable
        style="width: 260px"
        @clear="loadCities()"
        @keyup.enter="loadCities()"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <el-button type="primary" @click="loadCities()">🔍 搜索</el-button>
      <div style="flex: 1" />
      <el-button type="success" @click="openDialog(null)">➕ 新增城市</el-button>
    </div>

    <el-table :data="cities" border stripe style="width: 100%" max-height="calc(100vh - 200px)">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="name" label="名称" min-width="120" />
      <el-table-column prop="province" label="省份" width="100" />
      <el-table-column prop="hub_name" label="枢纽名" width="120" />
      <el-table-column prop="lat" label="纬度" width="100" />
      <el-table-column prop="lng" label="经度" width="100" />
      <el-table-column label="热门" width="80">
        <template #default="{ row }">
          <el-tag v-if="row.is_hot" type="success" size="small">热门</el-tag>
          <span v-else style="color: #c0c4cc; font-size: 12px">—</span>
        </template>
      </el-table-column>
      <el-table-column label="景点数" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.spot_count != null" size="small">{{ row.spot_count }}</el-tag>
          <span v-else style="color: #c0c4cc; font-size: 12px">—</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" link @click="openDialog(row)">编辑</el-button>
          <el-popconfirm
            title="确认删除该城市？此操作可能级联删除关联景点"
            @confirm="handleDelete(row)"
          >
            <template #reference>
              <el-button type="danger" size="small" link>删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="dialogVisible"
      :title="editing ? '编辑城市' : '新增城市'"
      width="500px"
      destroy-on-close
    >
      <el-form :model="form" label-width="90px" style="padding-right: 20px">
        <el-form-item label="城市名称">
          <el-input v-model="form.name" placeholder="请输入城市名称" />
        </el-form-item>
        <el-form-item label="省份">
          <el-input v-model="form.province" placeholder="例如：北京 / 广东" />
        </el-form-item>
        <el-form-item label="枢纽名">
          <el-input v-model="form.hub_name" placeholder="选填，默认与名称相同" />
        </el-form-item>
        <el-form-item label="纬度 lat">
          <el-input-number v-model="form.lat" :precision="6" :step="0.01" style="width: 100%" />
        </el-form-item>
        <el-form-item label="经度 lng">
          <el-input-number v-model="form.lng" :precision="6" :step="0.01" style="width: 100%" />
        </el-form-item>
        <el-form-item label="热门城市">
          <el-switch v-model="form.is_hot" />
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
import { getCitiesAdmin, createCity, updateCity, deleteCity, getSpotsAdmin } from '@/api/admin'

const search = ref('')
const cities = ref([])
const dialogVisible = ref(false)
const editing = ref(null)

const form = reactive({
  name: '', province: '', hub_name: '', lat: 30.0, lng: 120.0, is_hot: false,
})

async function loadCities() {
  try {
    const data = await getCitiesAdmin({ keyword: search.value || undefined })
    const payload = data.data || data
    cities.value = payload.items || payload.list || payload.cities || (Array.isArray(payload) ? payload : [])
  } catch (e) {
    console.error(e)
  }
}

function openDialog(row) {
  editing.value = row
  if (row) {
    Object.assign(form, {
      name: row.name || '',
      province: row.province || '',
      hub_name: row.hub_name || '',
      lat: Number(row.lat) || 30.0,
      lng: Number(row.lng) || 120.0,
      is_hot: !!row.is_hot,
    })
  } else {
    Object.assign(form, {
      name: '', province: '', hub_name: '', lat: 30.0, lng: 120.0, is_hot: false,
    })
  }
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!form.name) { ElMessage.warning('请输入城市名称'); return }
  try {
    if (editing.value) {
      await updateCity(editing.value.id, { ...form })
      ElMessage.success('更新成功')
    } else {
      await createCity({ ...form })
      ElMessage.success('新增成功')
    }
    dialogVisible.value = false
    loadCities()
  } catch (e) {
    console.error(e)
  }
}

async function handleDelete(row) {
  try {
    // 尝试先查看关联景点数
    let spotCountInfo = ''
    try {
      const spotsData = await getSpotsAdmin({ city_id: row.id })
      const spots = (spotsData.data || spotsData).items || (spotsData.data || spotsData).list || (Array.isArray(spotsData.data || spotsData) ? spotsData.data || spotsData : [])
      if (spots.length > 0) {
        spotCountInfo = `\n\n⚠️ 该城市下还有 ${spots.length} 个景点，删除城市将级联删除这些景点`
      }
    } catch {
      // 忽略，继续删除确认
    }

    await ElMessageBox.confirm(
      `确认删除城市 "${row.name}"？此操作不可恢复${spotCountInfo}`,
      '删除确认',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' }
    )
    await deleteCity(row.id)
    ElMessage.success('删除成功')
    loadCities()
  } catch (e) {
    if (e !== 'cancel') console.error(e)
  }
}

onMounted(loadCities)
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
</style>
