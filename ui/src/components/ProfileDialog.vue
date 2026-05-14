<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { authApi } from '@/services/auth'
import { ElMessage, ElMessageBox } from 'element-plus'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits(['update:modelValue'])
const router = useRouter()

const visible = ref(props.modelValue)
watch(() => props.modelValue, (v) => { visible.value = v })
watch(visible, (v) => { emit('update:modelValue', v) })

const activeTab = ref('account')
const profile = ref<any>({})

watch(visible, async (v) => {
  if (v) {
    const { data } = await authApi.getProfile()
    profile.value = data
  }
})

async function editField(field: string, label: string, current: string) {
  try {
    const { value } = await ElMessageBox.prompt(`新${label}`, `修改${label}`, { inputValue: current })
    if (!value) return
    const body: any = {}; body[field] = value
    await authApi.updateProfile(body)
    ElMessage.success('已更新')
    // 用户名/邮箱改完需重新登录
    if (field === 'username' || field === 'email') {
      logout()
    } else {
      const { data } = await authApi.getProfile()
      profile.value = data
    }
  } catch { /* 取消 */ }
}

async function changePwd() {
  try {
    const { value: oldPwd } = await ElMessageBox.prompt('原密码', '修改密码', { inputType: 'password' })
    if (!oldPwd) return
    let newPwd = ''
    while (true) {
      const result = await ElMessageBox.prompt('新密码（至少6位）', '修改密码', {
        inputType: 'password',
        inputErrorMessage: '密码至少6位',
      }).catch(() => null)
      if (!result) return
      newPwd = result.value || ''
      if (newPwd.length >= 6) break
      ElMessage.warning('密码至少需要6位')
    }
    await authApi.changePassword(oldPwd, newPwd)
    ElMessage.success('密码已修改，请重新登录')
    logout()
  } catch (err: any) {
    if (err?.response) ElMessage.error(err.response.data?.detail || '修改失败')
  }
}

function logout() {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  router.push('/login')
}

</script>

<template>
  <el-dialog v-model="visible" width="580px" :show-close="false" :close-on-click-modal="false">
    <template #header>
      <div class="dlg-header">
        <span class="dlg-title">设置</span>
        <el-button text class="dlg-close" @click="visible = false">
          <el-icon><svg viewBox="0 0 24 24" width="18" height="18"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" fill="currentColor"/></svg></el-icon>
        </el-button>
      </div>
    </template>

    <div class="dlg-body">
      <!-- 左导航 -->
      <el-menu :default-active="activeTab" class="dlg-nav">
        <div class="nav-title">通用</div>
        <el-menu-item index="account">账号管理</el-menu-item>
        <el-menu-item index="preferences" disabled>偏好设置</el-menu-item>
      </el-menu>

      <!-- 右内容 -->
      <div class="dlg-content">
        <!-- 用户卡片 -->
        <div class="user-card">
          <el-avatar :size="48" class="user-avatar">医</el-avatar>
          <div class="user-meta">
            <span class="user-name">{{ profile.username || '—' }}</span>
            <el-tag size="small" type="info">{{ profile.role === 'admin' ? '管理员' : '医生' }}</el-tag>
          </div>
        </div>

        <!-- 字段列表 -->
        <div class="field-card">
          <div class="field-row">
            <span class="field-label">用户名</span>
            <span class="field-val">{{ profile.username || '—' }}</span>
            <el-button link type="primary" @click="editField('username', '用户名', profile.username || '')">修改</el-button>
          </div>
          <div class="field-row">
            <span class="field-label">邮箱</span>
            <span class="field-val">{{ profile.email || '未绑定' }}</span>
            <el-button link type="primary" @click="editField('email', '邮箱', profile.email || '')">修改</el-button>
          </div>
          <div class="field-row">
            <span class="field-label">医院</span>
            <span class="field-val">{{ profile.hospital || '未填写' }}</span>
            <el-button link type="primary" @click="editField('hospital', '医院', profile.hospital || '')">修改</el-button>
          </div>
          <div class="field-row">
            <span class="field-label">科室</span>
            <span class="field-val">{{ profile.department || '未填写' }}</span>
            <el-button link type="primary" @click="editField('department', '科室', profile.department || '')">修改</el-button>
          </div>
          <div class="field-row">
            <span class="field-label">密码</span>
            <span class="field-val">••••••••</span>
            <el-button link type="primary" @click="changePwd">修改</el-button>
          </div>
        </div>

        <el-button text type="danger" class="logout-btn" @click="logout">退出登录</el-button>
      </div>
    </div>
  </el-dialog>
</template>

<style scoped>
.dlg-header { display: flex; align-items: center; justify-content: space-between; }
.dlg-title { font-size: 18px; font-weight: 600; }
.dlg-close { color: #999; }

.dlg-body { display: flex; margin-top: 8px; }

/* 左导航 */
.dlg-nav { width: 130px; border-right: none; flex-shrink: 0; }
.dlg-nav .nav-title { font-size: 12px; color: #bbb; padding: 8px 20px; }
.dlg-nav .el-menu-item { height: 38px; line-height: 38px; font-size: 13px; }

/* 右内容 */
.dlg-content { flex: 1; padding-left: 20px; }

.user-card { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
.user-avatar { background: linear-gradient(135deg, #409EFF, #67C23A); font-size: 18px; }
.user-meta { display: flex; flex-direction: column; gap: 2px; }
.user-name { font-size: 16px; font-weight: 600; color: #222; }

.field-card { background: #fafafa; border-radius: 10px; padding: 4px 16px; margin-bottom: 20px; }
.field-card .el-divider { margin: 0; }
.field-row { display: flex; align-items: center; padding: 14px 0; font-size: 14px; }
.field-label { width: 56px; color: #999; flex-shrink: 0; }
.field-val { flex: 1; color: #333; }

.logout-btn { display: block; margin: 0 auto; }
</style>
