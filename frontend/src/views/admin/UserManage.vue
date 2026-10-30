<template>
  <div class="page">
    <h3>👥 用户管理</h3>
    <p class="desc">管理平台所有注册用户，可修改角色或删除账号</p>

    <div class="toolbar">
      <el-input
        v-model="search"
        placeholder="搜索用户名或邮箱..."
        clearable
        style="width: 280px"
        @clear="loadUsers()"
        @keyup.enter="loadUsers()"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <el-button type="primary" @click="loadUsers()">🔍 搜索</el-button>
    </div>

    <el-table :data="users" border stripe style="width: 100%" max-height="calc(100vh - 200px)">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="username" label="用户名" min-width="140" />
      <el-table-column prop="email" label="邮箱" min-width="200" />
      <el-table-column label="角色" width="120">
        <template #default="{ row }">
          <el-tag :type="row.role === 'admin' ? 'danger' : 'primary'" effect="light">
            {{ row.role === 'admin' ? '管理员' : '普通用户' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="注册时间" width="180" />
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <div class="op-row">
            <el-select
              v-model="row.role"
              size="small"
              style="width: 100px"
              :disabled="row.id === currentUserId"
              @change="(v) => handleChangeRole(row, v)"
            >
              <el-option label="user" value="user" />
              <el-option label="admin" value="admin" />
            </el-select>
            <el-popconfirm
              :disabled="row.id === currentUserId"
              title="确认删除该用户？此操作不可恢复"
              @confirm="handleDelete(row)"
            >
              <template #reference>
                <el-button type="danger" size="small" :disabled="row.id === currentUserId">
                  删除
                </el-button>
              </template>
            </el-popconfirm>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-wrap">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="loadUsers"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getUsers, updateUserRole, deleteUser } from '@/api/admin'

const search = ref('')
const users = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20

const currentUserId = computed(() => {
  const user = JSON.parse(localStorage.getItem('user') || 'null')
  return user?.id
})

async function loadUsers() {
  try {
    const data = await getUsers({
      page: page.value,
      per_page: pageSize,
      keyword: search.value || undefined,
    })
    // 兼容不同返回格式
    const payload = data.data || data
    users.value = payload.items || payload.list || payload.users || (Array.isArray(payload) ? payload : [])
    total.value = payload.total ?? (Array.isArray(payload) ? payload.length : 0)
  } catch (e) {
    console.error(e)
  }
}

async function handleChangeRole(row, newRole) {
  try {
    await updateUserRole(row.id, newRole)
    ElMessage.success('角色修改成功')
    loadUsers()
  } catch (e) {
    // 失败时回滚
    row.role = row.role === 'admin' ? 'user' : 'admin'
    ElMessage.error('角色修改失败')
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确认删除用户 "${row.username}"？此操作不可恢复`,
      '删除确认',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' }
    )
    await deleteUser(row.id)
    ElMessage.success('删除成功')
    loadUsers()
  } catch (e) {
    if (e !== 'cancel') console.error(e)
  }
}

onMounted(loadUsers)
</script>

<style scoped>
.page {
  padding: 16px;
  background: #f5f7fa;
  min-height: calc(100vh - 120px);
}
.page h3 {
  margin: 0 0 4px;
  color: #1f2937;
  font-size: 18px;
}
.desc {
  color: #6b7280;
  font-size: 13px;
  margin: 0 0 12px;
}
.toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 12px;
  background: #fff;
  padding: 12px;
  border-radius: 6px;
  border: 1px solid #ebeef5;
}
.op-row {
  display: flex;
  gap: 8px;
  align-items: center;
}
.pagination-wrap {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
</style>
