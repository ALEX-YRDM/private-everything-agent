<script setup lang="ts">
import { NTag, NEmpty } from 'naive-ui'
import { useSettingsStore } from '../../stores/settings'

const settings = useSettingsStore()
</script>

<template>
  <div class="section">
    <div class="section-header">
      <div>
        <h4 style="margin:0">系统技能（{{ settings.systemSkills.length }}）</h4>
        <p class="hint" style="margin:4px 0 0">模型可通过 <code>read_skill</code> 按需读取，技能名称和描述已注入到对话上下文。</p>
      </div>
    </div>
  </div>
  <NEmpty v-if="settings.systemSkills.length === 0" description="暂无系统技能" style="margin: 24px 0" />
  <div v-else class="skill-list">
    <div v-for="skill in settings.systemSkills" :key="skill.name" class="skill-row">
      <div class="skill-info">
        <div class="skill-title-row">
          <code class="skill-name">{{ skill.name }}</code>
          <NTag v-if="!skill.available" size="tiny" type="warning">依赖缺失</NTag>
        </div>
        <p class="skill-desc">{{ skill.description }}</p>
        <p v-if="skill.requires_bins.length || skill.requires_env.length" class="skill-requires">
          <span v-if="skill.requires_bins.length">需要命令：{{ skill.requires_bins.join(', ') }}</span>
          <span v-if="skill.requires_env.length">需要环境变量：{{ skill.requires_env.join(', ') }}</span>
        </p>
      </div>
    </div>
  </div>

  <div class="section" style="margin-top:24px">
    <div>
      <h4 style="margin:0">用户自定义技能（{{ settings.userSkills.length }}）</h4>
      <p class="hint" style="margin:4px 0 0">放在 <code>workspace/skills/</code> 目录下，每个子目录含一个 <code>SKILL.md</code>，模型可按需读取。</p>
    </div>
    <NEmpty v-if="settings.userSkills.length === 0" description="workspace/skills/ 下暂无自定义技能" :style="{ margin: '12px 0' }" />
    <div v-else class="skill-list">
      <div v-for="skill in settings.userSkills" :key="skill.name" class="skill-row">
        <div class="skill-info">
          <div class="skill-title-row">
            <code class="skill-name">{{ skill.name }}</code>
            <NTag size="tiny" type="info">用户技能</NTag>
          </div>
          <p class="skill-desc">{{ skill.description }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@import './settings-common.css';
</style>