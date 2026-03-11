<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { NDrawer, NDrawerContent, NSelect, NDivider, NTag, NDescriptions, NDescriptionsItem } from 'naive-ui'
import { useSettingsStore } from '../stores/settings'

const settings = useSettingsStore()

const modelOptions = computed(() =>
  settings.models.map((m) => ({
    label: `${m.id} (${m.provider})`,
    value: m.id,
  }))
)

onMounted(() => {
  settings.loadModels()
})
</script>

<template>
  <NDrawer v-model:show="settings.showSettings" :width="360" placement="right">
    <NDrawerContent title="⚙️ 设置" :native-scrollbar="false">
      <div class="settings-section">
        <h4>模型配置</h4>
        <div class="setting-item">
          <label>当前模型</label>
          <NSelect
            v-model:value="settings.currentModel"
            :options="modelOptions"
            filterable
            @update:value="settings.setModel"
          />
        </div>
      </div>

      <NDivider />

      <div class="settings-section">
        <h4>已注册工具</h4>
        <div class="tools-list">
          <NTag
            v-for="tool in settings.tools"
            :key="tool"
            size="small"
            type="info"
            style="margin: 2px"
          >
            {{ tool }}
          </NTag>
          <span v-if="settings.tools.length === 0" class="empty-text">暂无工具</span>
        </div>
      </div>

      <NDivider />

      <div class="settings-section">
        <h4>系统配置</h4>
        <NDescriptions :column="1" size="small" bordered>
          <NDescriptionsItem
            v-for="(value, key) in settings.config"
            :key="key"
            :label="String(key)"
          >
            {{ typeof value === 'object' ? JSON.stringify(value) : String(value) }}
          </NDescriptionsItem>
        </NDescriptions>
      </div>
    </NDrawerContent>
  </NDrawer>
</template>

<style scoped>
.settings-section {
  margin-bottom: 8px;
}

.settings-section h4 {
  font-size: 13px;
  font-weight: 600;
  color: #555;
  margin-bottom: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.setting-item {
  margin-bottom: 14px;
}

.setting-item label {
  display: block;
  font-size: 13px;
  color: #666;
  margin-bottom: 6px;
}

.tools-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.empty-text {
  font-size: 13px;
  color: #aaa;
}
</style>
