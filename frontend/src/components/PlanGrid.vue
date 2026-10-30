<template>
  <div class="grid-wrap">
    <el-empty v-if="!plans.length" :description="empty || '暂无数据'" />
    <div v-else class="plan-grid">
      <div v-for="p in plans" :key="p.id" class="card" @click="$emit('open', p)">
        <div class="pc-cover" :style="coverStyle(p)">
          <span class="pc-route">
            {{ cityName(p.start_city_id) }} → {{ cityName(p.end_city_id) }}
          </span>
          <span v-if="p.is_public" class="pc-tag pub">🌐</span>
          <span v-else class="pc-tag pri">🔒</span>
        </div>
        <div class="card-body">
          <div class="stats">
            <div class="s-item"><strong class="val-time">{{ formatTime(p.total_time) }}</strong><span>⏱</span></div>
            <div class="s-item"><strong class="val-money">¥{{ p.total_money }}</strong><span>💰</span></div>
          </div>
          <div class="foot">
            <div class="foot-left">
              <el-rate v-if="p.rating" :model-value="p.rating" disabled :max="5" size="small" />
              <span v-if="p.spot_ids?.length" class="spot-count">🏞️ {{ p.spot_ids.length }}</span>
            </div>
            <span class="time">{{ p.created_at }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps(['plans', 'cityMap', 'empty'])
defineEmits(['open'])

function cityName(id) { return props.cityMap?.[id] || ('#' + id) }
function formatTime(min) {
  const h = Math.floor(min / 60), m = min % 60
  return h ? `${h}h ${m}min` : `${m}min`
}

const gradients = [
  'linear-gradient(135deg,#7c3aed,#ec4899)',
  'linear-gradient(135deg,#0ea5e9,#6366f1)',
  'linear-gradient(135deg,#f97316,#e11d48)',
  'linear-gradient(135deg,#10b981,#0ea5e9)',
  'linear-gradient(135deg,#f59e0b,#ef4444)',
]
function coverStyle(p) {
  const idx = (p.start_city_id + p.end_city_id) % gradients.length
  return { background: gradients[idx] }
}
</script>

<style scoped>
.grid-wrap { padding: 12px 0; }
.plan-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 14px; }
.card {
  background: #fff; border-radius: 12px; overflow: hidden;
  cursor: pointer; border: 1px solid #e5e7eb;
  transition: all 0.25s;
}
.card:hover { box-shadow: 0 8px 24px rgba(124,58,237,0.15); border-color: #7c3aed; transform: translateY(-3px); }
.pc-cover {
  height: 70px; display: flex; align-items: center; justify-content: center;
  position: relative;
}
.pc-route {
  color: #fff; font-weight: 700; font-size: 15px;
  text-shadow: 0 2px 6px rgba(0,0,0,0.2);
}
.pc-tag {
  position: absolute; top: 6px; right: 8px; font-size: 14px;
  width: 26px; height: 26px; border-radius: 50%;
  background: rgba(255,255,255,0.9);
  display: flex; align-items: center; justify-content: center;
}
.card-body { padding: 12px 14px; }
.stats { display: flex; gap: 16px; margin-bottom: 8px; }
.s-item { display: flex; align-items: center; gap: 4px; font-size: 14px; }
.s-item .val-time { color: #2563eb; }
.s-item .val-money { color: #059669; }
.foot { display: flex; justify-content: space-between; align-items: center; }
.foot-left { display: flex; align-items: center; gap: 10px; }
.spot-count { font-size: 12px; color: #f59e0b; }
.time { font-size: 11px; color: #9ca3af; }
</style>
