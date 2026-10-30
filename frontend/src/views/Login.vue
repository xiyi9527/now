<template>
  <div class="login-page" ref="pageRef">
    <!-- 动态渐变背景 -->
    <div class="bg-gradient"></div>
    <!-- 漂浮粒子 -->
    <div class="particles">
      <span v-for="i in 30" :key="i" :class="'p p'+(i%10+1)"
            :style="{
              '--d': (i*0.5)+'s',
              '--x': (i*37)+'px',
              '--y': (i*53)+'px',
              '--s': (0.5 + (i%7)*0.25),
              '--dur': (6 + (i%5)*2) + 's',
            }"></span>
    </div>
    <!-- 漂浮景点 emoji -->
    <div class="emojis">
      <span v-for="(e, i) in floatEmojis" :key="i" class="emoji"
            :style="{ left: e.x+'%', top: e.y+'%', animationDelay: e.delay+'s', fontSize: e.size+'px' }">
        {{ e.char }}
      </span>
    </div>
    <!-- 光线 -->
    <div class="light-rays">
      <span v-for="i in 6" :key="i" :style="{ '--rot': (i*30)+'deg' }"></span>
    </div>

    <div class="login-card-wrap" :style="cardStyle">
      <!-- 左侧品牌区 -->
      <div class="brand-side">
        <div class="brand-logo">
          <span class="logo-inner">🧭</span>
        </div>
        <h1 class="brand-title">
          <span v-for="(c, i) in '智能旅行规划'" :key="i"
                class="title-char" :style="{ animationDelay: (0.1 + i*0.1)+'s' }">{{ c }}</span>
        </h1>
        <p class="brand-sub">基于 NSGA-II 多目标优化算法</p>
        <ul class="feature-list">
          <li v-for="(f, i) in features" :key="i"
              class="feature-item" :style="{ animationDelay: (0.4 + i*0.15)+'s' }">
            <span class="f-icon">{{ f.icon }}</span>
            <span>{{ f.text }}</span>
          </li>
        </ul>
        <div class="brand-stats">
          <div class="stat">
            <strong>20+</strong><span>城市</span>
          </div>
          <div class="stat">
            <strong>NSGA-II</strong><span>算法</span>
          </div>
          <div class="stat">
            <strong>∞</strong><span>路线</span>
          </div>
        </div>
      </div>

      <!-- 右侧表单 -->
      <div class="form-side">
        <div class="form-header">
          <h2 class="form-title">{{ mode === 'login' ? '欢迎回来' : '开启旅程' }}</h2>
          <p class="form-sub">{{ mode === 'login' ? '登录继续探索世界 🌍' : '注册开始你的第一次规划 ✨' }}</p>
        </div>

        <el-tabs v-model="mode" class="mode-tabs">
          <el-tab-pane label="登录" name="login">
            <el-form label-position="top">
              <div class="floating-input">
                <input v-model="loginForm.username" id="login-user" placeholder=" " />
                <label for="login-user">👤 用户名</label>
              </div>
              <div class="floating-input">
                <input v-model="loginForm.password" id="login-pwd" type="password" placeholder=" " />
                <label for="login-pwd">🔒 密码</label>
              </div>
              <button type="button" class="submit-btn" :disabled="loading" @click="handleLogin">
                <span v-if="!loading">立即登录 🚀</span>
                <span v-else>登录中...</span>
                <span class="btn-shine"></span>
              </button>
            </el-form>
          </el-tab-pane>

          <el-tab-pane label="注册" name="register">
            <el-form label-position="top">
              <div class="floating-input">
                <input v-model="regForm.username" id="reg-user" placeholder=" " autocomplete="username" />
                <label for="reg-user">👤 用户名（≥2字符）</label>
              </div>
              <div class="floating-input">
                <input v-model="regForm.password" id="reg-pwd" type="password" placeholder=" " autocomplete="new-password" />
                <label for="reg-pwd">🔒 密码（≥6字符）</label>
              </div>
              <div class="floating-input">
                <input v-model="regForm.email" id="reg-email" placeholder=" " type="email" />
                <label for="reg-email">📧 邮箱（可选）</label>
              </div>
              <button type="button" class="submit-btn" :disabled="loading" @click="handleRegister">
                <span v-if="!loading">开始旅行 ✈️</span>
                <span v-else>注册中...</span>
                <span class="btn-shine"></span>
              </button>
            </el-form>
          </el-tab-pane>
        </el-tabs>

        <div class="form-footer">
          <span>💡 小贴士：选好起点终点，AI 帮你规划多条"时间-金钱-体验"折中的最优路线</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { apiLogin, apiRegister } from '../api'
import { useUserStore } from '../stores/user'

const mode = ref('login')
const loading = ref(false)
const router = useRouter()
const userStore = useUserStore()

const loginForm = reactive({ username: '', password: '' })
const regForm = reactive({ username: '', password: '', email: '' })

const features = [
  { icon: '🧠', text: '智能多目标优化' },
  { icon: '🗺️', text: '地图实时联动' },
  { icon: '🏞️', text: '景点一键加入' },
  { icon: '⭐', text: '评价分享行程' },
]

const floatEmojis = [
  { char: '🌄', x: 8, y: 15, size: 42, delay: 0 },
  { char: '✈️', x: 85, y: 10, size: 38, delay: 1 },
  { char: '🗺️', x: 15, y: 75, size: 46, delay: 2 },
  { char: '🧳', x: 78, y: 80, size: 40, delay: 0.5 },
  { char: '🏖️', x: 50, y: 5, size: 34, delay: 1.5 },
  { char: '⛰️', x: 3, y: 45, size: 38, delay: 2.5 },
  { char: '🏯', x: 92, y: 50, size: 36, delay: 3 },
  { char: '🚗', x: 35, y: 88, size: 32, delay: 0.8 },
]

async function handleLogin() {
  if (!loginForm.username || !loginForm.password) { ElMessage.warning('请填写用户名和密码'); return }
  loading.value = true
  try {
    const d = await apiLogin(loginForm)
    if (d.ok) { userStore.login(d); ElMessage.success('🎉 登录成功'); router.push('/plan') }
    else ElMessage.error(d.msg || '登录失败')
  } catch {} finally { loading.value = false }
}
async function handleRegister() {
  if (!regForm.username || !regForm.password) { ElMessage.warning('请填写用户名和密码'); return }
  loading.value = true
  try {
    const d = await apiRegister(regForm)
    if (d.ok) { userStore.login(d); ElMessage.success('🎉 注册成功'); router.push('/plan') }
    else ElMessage.error(d.msg || '注册失败')
  } catch {} finally { loading.value = false }
}

// 鼠标 3D 倾斜
const pageRef = ref(null)
const tilt = reactive({ x: 0, y: 0 })
const cardStyle = computed(() => ({
  transform: `perspective(1200px) rotateX(${tilt.x}deg) rotateY(${tilt.y}deg)`,
}))
let rafId = null
function onMove(e) {
  if (!pageRef.value) return
  const rect = pageRef.value.getBoundingClientRect()
  const cx = rect.width / 2, cy = rect.height / 2
  const dx = (e.clientX - rect.left - cx) / cx
  const dy = (e.clientY - rect.top - cy) / cy
  tilt.y = dx * 5
  tilt.x = -dy * 4
}
function onLeave() { tilt.x = 0; tilt.y = 0 }
onMounted(() => {
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseleave', onLeave)
})
onUnmounted(() => {
  window.removeEventListener('mousemove', onMove)
  window.removeEventListener('mouseleave', onLeave)
  if (rafId) cancelAnimationFrame(rafId)
})
</script>

<style scoped>
.login-page {
  min-height: 100vh; display: flex; align-items: center; justify-content: center;
  position: relative; overflow: hidden;
}

/* 动态渐变背景 —— 流光效果 */
.bg-gradient {
  position: absolute; inset: 0; z-index: -2;
  background: linear-gradient(-45deg, #0f172a, #1e3a8a, #7c3aed, #ec4899, #f97316, #0ea5e9);
  background-size: 400% 400%;
  animation: flow 18s ease infinite;
}
@keyframes flow {
  0%   { background-position: 0% 50%; }
  50%  { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}

/* 光线 */
.light-rays {
  position: absolute; inset: 0; z-index: -1; overflow: hidden; pointer-events: none;
}
.light-rays span {
  position: absolute; top: 50%; left: 50%;
  width: 200%; height: 2px;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.08), transparent);
  transform-origin: 0% 50%;
  transform: rotate(var(--rot)) translateY(-50%);
  animation: ray-shimmer 8s ease-in-out infinite;
  animation-delay: calc(var(--rot) * 0.02s);
}
@keyframes ray-shimmer {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 0.8; }
}

/* 漂浮粒子 */
.particles { position: absolute; inset: 0; z-index: -1; }
.particles .p {
  position: absolute; width: 10px; height: 10px; border-radius: 50%;
  background: rgba(255,255,255,0.15);
  transform: translate(calc(var(--x) * 1px), calc(var(--y) * 1px)) scale(var(--s));
  animation: float-up var(--dur) ease-in-out infinite;
  animation-delay: calc(var(--d) * 1s);
  box-shadow: 0 0 8px rgba(255,255,255,0.3);
}
.particles .p.p2, .particles .p.p7 { width: 16px; height: 16px; background: rgba(255,255,255,0.1); }
.particles .p.p4, .particles .p.p9 { width: 6px; height: 6px;  background: rgba(255,255,255,0.3); }
@keyframes float-up {
  0%, 100% { transform: translate(calc(var(--x) * 1px), calc(var(--y) * 1px)) scale(var(--s)); opacity: 0.3; }
  50%      { transform: translate(calc(var(--x) * 1px + 30px), calc(var(--y) * 1px - 50px)) scale(calc(var(--s) * 1.3)); opacity: 1; }
}

/* 漂浮景点 emoji */
.emojis { position: absolute; inset: 0; z-index: -1; pointer-events: none; }
.emojis .emoji {
  position: absolute; animation: emoji-float 12s ease-in-out infinite;
  filter: drop-shadow(0 4px 12px rgba(0,0,0,0.3));
  opacity: 0.85;
}
@keyframes emoji-float {
  0%, 100% { transform: translateY(0) rotate(-8deg); }
  25% { transform: translateY(-25px) rotate(8deg); }
  50% { transform: translateY(-10px) rotate(-4deg); }
  75% { transform: translateY(-35px) rotate(12deg); }
}

/* 主卡片 */
.login-card-wrap {
  display: flex; width: 860px; height: 540px;
  border-radius: 24px; overflow: hidden;
  box-shadow: 0 30px 80px rgba(0,0,0,0.4);
  backdrop-filter: blur(16px);
  animation: card-in 0.8s cubic-bezier(0.16,1,0.3,1);
  will-change: transform;
  transition: transform 0.15s ease-out;
}
@keyframes card-in {
  from { opacity: 0; transform: translateY(40px) scale(0.92); }
  to   { opacity: 1; transform: none; }
}

/* 左侧品牌区 */
.brand-side {
  width: 42%; background: rgba(255,255,255,0.1);
  backdrop-filter: blur(12px);
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 40px 30px; color: #fff;
  border-right: 1px solid rgba(255,255,255,0.2);
  position: relative; overflow: hidden;
}
.brand-side::before {
  content: ''; position: absolute; inset: -50%;
  background: conic-gradient(from 0deg, transparent, rgba(255,255,255,0.05), transparent);
  animation: rotate-bg 20s linear infinite;
}
@keyframes rotate-bg { to { transform: rotate(360deg); } }

.brand-logo {
  width: 84px; height: 84px; border-radius: 50%;
  background: rgba(255,255,255,0.2);
  display: flex; align-items: center; justify-content: center;
  margin-bottom: 24px;
  animation: logo-spin 14s linear infinite;
  position: relative; z-index: 1;
  box-shadow: 0 0 30px rgba(255,255,255,0.2);
}
.brand-logo .logo-inner { font-size: 40px; }
@keyframes logo-spin { to { transform: rotate(360deg); } }

.brand-title { font-size: 28px; margin: 0 0 8px; letter-spacing: 3px; position: relative; z-index: 1; }
.title-char {
  display: inline-block;
  animation: char-pop 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) both;
}
@keyframes char-pop {
  from { opacity: 0; transform: translateY(-20px); }
  to   { opacity: 1; transform: none; }
}

.brand-sub { font-size: 13px; opacity: 0.85; margin: 0 0 28px; position: relative; z-index: 1; }
.feature-list { list-style: none; padding: 0; margin: 0; position: relative; z-index: 1; }
.feature-item {
  padding: 8px 0; font-size: 14px; opacity: 0.9;
  display: flex; gap: 10px; align-items: center;
  animation: fade-slide 0.5s ease both;
}
.feature-item .f-icon {
  width: 28px; height: 28px; border-radius: 8px;
  background: rgba(255,255,255,0.2);
  display: flex; align-items: center; justify-content: center;
  font-size: 14px;
}
@keyframes fade-slide {
  from { opacity: 0; transform: translateX(-15px); }
  to   { opacity: 0.9; transform: none; }
}
.brand-stats {
  margin-top: 28px; display: flex; gap: 20px;
  padding-top: 18px; border-top: 1px solid rgba(255,255,255,0.2);
  position: relative; z-index: 1;
}
.brand-stats .stat {
  display: flex; flex-direction: column; align-items: center;
}
.brand-stats strong { font-size: 18px; font-weight: 700; }
.brand-stats span { font-size: 10px; opacity: 0.7; }

/* 右侧表单 */
.form-side {
  width: 58%; background: #fff;
  padding: 40px 44px 32px;
  display: flex; flex-direction: column;
}
.form-header { margin-bottom: 22px; }
.form-title {
  font-size: 26px; color: #1f2937; margin: 0 0 4px;
  animation: title-glow 2s ease-in-out infinite alternate;
}
@keyframes title-glow {
  from { color: #1f2937; }
  to   { color: #7c3aed; }
}
.form-sub { color: #9ca3af; font-size: 13px; margin: 0; }

.mode-tabs :deep(.el-tabs__item) { font-size: 15px; }
.mode-tabs :deep(.el-tabs__active-bar) {
  height: 3px; border-radius: 2px;
  background: linear-gradient(90deg, #7c3aed, #ec4899);
}

/* 浮动 label 输入框 */
.floating-input {
  position: relative; margin-bottom: 18px;
}
.floating-input input {
  width: 100%; padding: 18px 14px 8px;
  border: 1.5px solid #e5e7eb; border-radius: 10px;
  font-size: 14px; color: #1f2937;
  transition: all 0.25s;
  background: #fafbfc;
  outline: none;
  box-sizing: border-box;
}
.floating-input input:focus {
  border-color: #7c3aed; background: #fff;
  box-shadow: 0 0 0 4px rgba(124,58,237,0.1);
}
.floating-input label {
  position: absolute; top: 16px; left: 14px;
  font-size: 13px; color: #9ca3af;
  pointer-events: none;
  transition: all 0.25s;
  background: transparent;
  padding: 0 4px;
}
.floating-input input:focus + label,
.floating-input input:not(:placeholder-shown) + label {
  top: 6px; font-size: 10px; color: #7c3aed; font-weight: 600;
}

/* 提交按钮 */
.submit-btn {
  width: 100%; margin-top: 8px; height: 48px; border: none; border-radius: 12px;
  background: linear-gradient(135deg, #7c3aed, #ec4899);
  color: #fff; font-size: 16px; font-weight: 600; letter-spacing: 2px;
  cursor: pointer; position: relative; overflow: hidden;
  transition: all 0.3s;
}
.submit-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 10px 30px rgba(124,58,237,0.45);
}
.submit-btn:active:not(:disabled) { transform: translateY(0); }
.submit-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.submit-btn .btn-shine {
  position: absolute; top: 0; left: -100%; width: 100%; height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
  animation: shine 3s infinite;
}
@keyframes shine {
  0%   { left: -100%; }
  60%  { left: -100%; }
  80%  { left: 100%; }
  100% { left: 100%; }
}

/* 表单底部提示 */
.form-footer {
  margin-top: auto; padding-top: 18px;
  border-top: 1px dashed #e5e7eb;
  font-size: 11px; color: #9ca3af; line-height: 1.6;
}
</style>
