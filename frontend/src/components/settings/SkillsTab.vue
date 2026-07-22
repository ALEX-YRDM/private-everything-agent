<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { NTag, NButton, NEmpty, NModal, NInput, NRadioGroup, NRadio, NSpin, NPopconfirm, useMessage } from 'naive-ui'
import { useSettingsStore, type Skill } from '../../stores/settings'
import type { SkillDetail } from '../../api/http'

const settings = useSettingsStore()
const message = useMessage()

onMounted(() => {
  settings.loadSkills()
})

/** 分组：user tier 在前，builtin 在后 */
const userSkills = computed(() => settings.skills.filter((s) => s.tier === 'user'))
const builtinSkills = computed(() => settings.skills.filter((s) => s.tier === 'builtin'))

// ── 安装 modal ──────────────────────────────────────────────
const showInstall = ref(false)
const installSource = ref<'path' | 'git'>('path')
const installLocation = ref('')
const installing = ref(false)

function openInstall() {
  installSource.value = 'path'
  installLocation.value = ''
  showInstall.value = true
}

async function doInstall() {
  const loc = installLocation.value.trim()
  if (!loc) { message.warning('请输入路径或 URL'); return }
  installing.value = true
  try {
    await settings.installSkill(installSource.value, loc)
    message.success('安装成功')
    showInstall.value = false
  } catch (e: any) {
    message.error(`安装失败：${e?.message || String(e)}`)
  } finally {
    installing.value = false
  }
}

// ── 详情 modal ──────────────────────────────────────────────
const showDetail = ref(false)
const detail = ref<SkillDetail | null>(null)
const detailLoading = ref(false)

async function openDetail(skill: Skill) {
  showDetail.value = true
  detailLoading.value = true
  detail.value = null
  try {
    detail.value = await settings.getSkillDetail(skill.name)
  } catch (e: any) {
    message.error(`加载失败：${e?.message || String(e)}`)
    showDetail.value = false
  } finally {
    detailLoading.value = false
  }
}

// ── 删除 ────────────────────────────────────────────────────
async function doRemove(name: string) {
  try {
    await settings.removeSkill(name)
    message.success(`已删除 ${name}`)
  } catch (e: any) {
    message.error(`删除失败：${e?.message || String(e)}`)
  }
}
</script>

<template>
  <div class="section">
    <div class="section-header">
      <div>
        <h4 style="margin:0">用户技能（{{ userSkills.length }}）</h4>
        <p class="hint" style="margin:4px 0 0">
          位于 <code>~/.mengdie/skills/</code>。可以手动安装现有 skill 目录，或让梦蝶通过 <code>skill-creator</code> 自己创建新技能。
        </p>
      </div>
      <NButton size="small" type="primary" @click="openInstall">+ 安装技能</NButton>
    </div>

    <NEmpty v-if="userSkills.length === 0" description="还没有用户技能" style="margin: 12px 0" />
    <div v-else class="skill-list">
      <div v-for="skill in userSkills" :key="skill.name" class="skill-row">
        <div class="skill-info" style="cursor:pointer" @click="openDetail(skill)">
          <div class="skill-title-row">
            <code class="skill-name">{{ skill.name }}</code>
            <NTag size="tiny" type="info">用户</NTag>
            <NTag v-if="!skill.available" size="tiny" type="warning">依赖缺失</NTag>
            <NTag v-if="skill.parse_error" size="tiny" type="error">解析异常</NTag>
          </div>
          <p class="skill-desc">{{ skill.description }}</p>
          <p v-if="skill.when" class="skill-when">
            <span class="when-label">触发：</span>{{ skill.when }}
          </p>
          <p v-if="skill.missing.length" class="skill-requires">
            缺失：{{ skill.missing.join(', ') }}
          </p>
        </div>
        <NPopconfirm @positive-click="doRemove(skill.name)">
          <template #trigger>
            <NButton size="tiny" tertiary type="error">删除</NButton>
          </template>
          删除用户技能 <code>{{ skill.name }}</code>？
        </NPopconfirm>
      </div>
    </div>
  </div>

  <div class="section" style="margin-top:24px">
    <div>
      <h4 style="margin:0">内置技能（{{ builtinSkills.length }}）</h4>
      <p class="hint" style="margin:4px 0 0">
        随代码发布的技能，位于项目 <code>./skills/</code>。同名用户技能会优先使用。
      </p>
    </div>
    <NEmpty v-if="builtinSkills.length === 0" description="暂无内置技能" style="margin: 12px 0" />
    <div v-else class="skill-list">
      <div v-for="skill in builtinSkills" :key="skill.name" class="skill-row">
        <div class="skill-info" style="cursor:pointer" @click="openDetail(skill)">
          <div class="skill-title-row">
            <code class="skill-name">{{ skill.name }}</code>
            <NTag v-if="!skill.available" size="tiny" type="warning">依赖缺失</NTag>
          </div>
          <p class="skill-desc">{{ skill.description }}</p>
          <p v-if="skill.when" class="skill-when">
            <span class="when-label">触发：</span>{{ skill.when }}
          </p>
          <p v-if="skill.missing.length" class="skill-requires">
            缺失：{{ skill.missing.join(', ') }}
          </p>
        </div>
      </div>
    </div>
  </div>

  <!-- 安装 modal -->
  <NModal v-model:show="showInstall" preset="card" title="安装技能" style="max-width: 520px">
    <div class="install-form">
      <div class="install-source">
        <NRadioGroup v-model:value="installSource">
          <NRadio value="path">本地目录</NRadio>
          <NRadio value="git">Git 仓库</NRadio>
        </NRadioGroup>
      </div>
      <NInput
        v-model:value="installLocation"
        :placeholder="installSource === 'path'
          ? '本地绝对路径（含 SKILL.md 的目录）'
          : 'git URL，如 https://github.com/xxx/some-skill.git'"
      />
      <div class="install-hint">
        <template v-if="installSource === 'path'">
          源目录会整个 copy 到 <code>~/.mengdie/skills/&lt;目录名&gt;/</code>，必须包含 SKILL.md。
        </template>
        <template v-else>
          执行 <code>git clone --depth=1</code> 到 <code>~/.mengdie/skills/&lt;仓库名&gt;/</code>，超时 60s。
        </template>
      </div>
      <div style="text-align:right; margin-top:16px">
        <NButton size="small" @click="showInstall = false" style="margin-right:8px">取消</NButton>
        <NButton size="small" type="primary" :loading="installing" @click="doInstall">安装</NButton>
      </div>
    </div>
  </NModal>

  <!-- 详情 modal -->
  <NModal
    v-model:show="showDetail"
    preset="card"
    :title="detail?.name || '技能详情'"
    style="max-width: 720px"
  >
    <div v-if="detailLoading" style="text-align:center; padding:24px">
      <NSpin size="small" /> 加载中…
    </div>
    <div v-else-if="detail">
      <div class="detail-meta">
        <NTag size="tiny" :type="detail.tier === 'user' ? 'info' : 'default'">{{ detail.tier }}</NTag>
        <NTag v-if="!detail.available" size="tiny" type="warning">依赖缺失</NTag>
        <span class="detail-path">{{ detail.path }}</span>
      </div>
      <p class="detail-desc">{{ detail.description }}</p>
      <p v-if="detail.when" class="detail-when">
        <strong>触发场景：</strong>{{ detail.when }}
      </p>
      <p v-if="detail.missing.length" class="detail-missing">
        <strong>缺失依赖：</strong>{{ detail.missing.join(', ') }}
      </p>
      <pre class="detail-content">{{ detail.content }}</pre>
    </div>
  </NModal>
</template>

<style scoped>
@import './settings-common.css';

.skill-when {
  margin: 4px 0 0;
  font-size: 11px;
  color: #6b7280;
}
.when-label {
  color: #9ca3af;
}

.install-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.install-source {
  display: flex;
  gap: 12px;
}
.install-hint {
  font-size: 11px;
  color: #9ca3af;
  line-height: 1.5;
}
.install-hint code {
  font-family: 'SF Mono', Monaco, monospace;
  background: #f3f4f6;
  padding: 1px 4px;
  border-radius: 3px;
  color: #374151;
}

.detail-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.detail-path {
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 11px;
  color: #9ca3af;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.detail-desc {
  margin: 0 0 8px;
  color: #374151;
  font-size: 13px;
}
.detail-when, .detail-missing {
  margin: 4px 0;
  font-size: 12px;
  color: #6b7280;
}
.detail-content {
  margin-top: 16px;
  padding: 12px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-x: auto;
  max-height: 400px;
  overflow-y: auto;
  color: #1f2937;
}
</style>
